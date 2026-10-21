#!/bin/bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
ENV_FILE=${PIGTRACKING_SYNC_ENV:-"$PROJECT_ROOT/.env.pigtracking-sync"}
PYTHON_BIN=${PIGTRACKING_PYTHON:-"$HOME/miniconda3/envs/pigtracking/bin/python"}

if [ ! -f "$ENV_FILE" ]; then
    echo "Configuration file not found: $ENV_FILE" >&2
    exit 1
fi

while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
        ''|'#'*) continue ;;
    esac
    name=${line%%=*}
    value=${line#*=}
    if [ "$name" = "PIGTRACKING_SYNC_SOURCE" ]; then
        if [[ "$value" == \"*\" && "$value" == *\" ]] ||
           [[ "$value" == \'*\' && "$value" == *\' ]]; then
            value=${value:1:${#value}-2}
        fi
        PIGTRACKING_SYNC_SOURCE=$value
    fi
done < "$ENV_FILE"

: "${PIGTRACKING_SYNC_SOURCE:?Missing PIGTRACKING_SYNC_SOURCE in $ENV_FILE}"
if [ ! -x "$PYTHON_BIN" ]; then
    echo "Python executable not found: $PYTHON_BIN" >&2
    exit 1
fi

case "${1:-}" in
    '') PERIOD_ARGS=(--last-hours 24) ;;
    --last-hours)
        [ "$#" -eq 2 ] || { echo "Usage: $0 [--last-hours HOURS | --since ISO_TIME [--until ISO_TIME]]" >&2; exit 2; }
        PERIOD_ARGS=(--last-hours "$2")
        ;;
    --since)
        [ "$#" -eq 2 ] || [ "$#" -eq 4 ] || { echo "Usage: $0 [--last-hours HOURS | --since ISO_TIME [--until ISO_TIME]]" >&2; exit 2; }
        PERIOD_ARGS=(--since "$2")
        if [ "$#" -eq 4 ] && [ "$3" = "--until" ]; then
            PERIOD_ARGS+=(--until "$4")
        elif [ "$#" -eq 4 ]; then
            echo "Expected --until after --since." >&2
            exit 2
        fi
        ;;
    *)
        echo "Usage: $0 [--last-hours HOURS | --since ISO_TIME [--until ISO_TIME]]" >&2
        exit 2
        ;;
esac

cd "$PROJECT_ROOT"
"$PYTHON_BIN" src/animaltracking/manage.py export_pen_activity \
    --output-root "$PIGTRACKING_SYNC_SOURCE/exports" \
    "${PERIOD_ARGS[@]}"
