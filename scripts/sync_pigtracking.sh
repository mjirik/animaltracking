#!/bin/bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
ENV_FILE=${PIGTRACKING_SYNC_ENV:-"$PROJECT_ROOT/.env.pigtracking-sync"}

if [ ! -f "$ENV_FILE" ]; then
    echo "Configuration file not found: $ENV_FILE" >&2
    echo "Copy .env.pigtracking-sync.example to .env.pigtracking-sync and edit its paths." >&2
    exit 1
fi

# Read only the two expected dotenv keys; do not execute the configuration.
while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
        ''|'#'*) continue ;;
    esac

    name=${line%%=*}
    value=${line#*=}
    case "$name" in
        PIGTRACKING_SYNC_SOURCE|PIGTRACKING_SYNC_DESTINATION_ROOT)
            if [[ "$value" == \"*\" && "$value" == *\" ]] ||
               [[ "$value" == \'*\' && "$value" == *\' ]]; then
                value=${value:1:${#value}-2}
            fi
            printf -v "$name" '%s' "$value"
            ;;
    esac
done < "$ENV_FILE"

: "${PIGTRACKING_SYNC_SOURCE:?Missing PIGTRACKING_SYNC_SOURCE in $ENV_FILE}"
: "${PIGTRACKING_SYNC_DESTINATION_ROOT:?Missing PIGTRACKING_SYNC_DESTINATION_ROOT in $ENV_FILE}"

if [ ! -d "$PIGTRACKING_SYNC_SOURCE" ]; then
    echo "Source directory does not exist: $PIGTRACKING_SYNC_SOURCE" >&2
    exit 1
fi
if [ ! -d "$PIGTRACKING_SYNC_DESTINATION_ROOT" ]; then
    echo "Destination root does not exist: $PIGTRACKING_SYNC_DESTINATION_ROOT" >&2
    exit 1
fi
if ! command -v rsync >/dev/null 2>&1; then
    echo "rsync is not installed or not available in PATH." >&2
    exit 1
fi

SOURCE_NAME=$(basename -- "${PIGTRACKING_SYNC_SOURCE%/}")
DESTINATION="${PIGTRACKING_SYNC_DESTINATION_ROOT%/}/$SOURCE_NAME"
RSYNC_ARGS=(-a --human-readable --info=progress2)

case "${1:-}" in
    '') ;;
    --dry-run|-n) RSYNC_ARGS+=(--dry-run --itemize-changes) ;;
    *)
        echo "Usage: $0 [--dry-run|-n]" >&2
        exit 2
        ;;
esac

echo "Synchronizing:"
echo "  from: $PIGTRACKING_SYNC_SOURCE/"
echo "  to:   $DESTINATION/"

rsync "${RSYNC_ARGS[@]}" -- "$PIGTRACKING_SYNC_SOURCE/" "$DESTINATION/"
