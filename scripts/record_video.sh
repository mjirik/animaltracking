#!/bin/bash

# echo "deb http://archive.ubuntu.com/ubuntu/ focal main restricted universe multiverse" | sudo tee -a /etc/apt/sources.list
# sudo apt-get update
# sudo apt-get install sshfs livemedia-utils

DATADIR="${DATADIR:-$HOME/data/biomedical}"

# mkdir -p ~/mnt/biomedical
# sshfs $USER@storage-plzen4.kky.zcu.cz:/data-ntis/projects/korpusy_cv/biomedical ~/mnt/biomedical

# Load .env without splitting values on whitespace.  The previous xargs-based
# version turned e.g. "[0, 0, 1, 1]" into several arguments to `export`.
ENV_FILE="${ENV_FILE:-.env}"
if [ -f "$ENV_FILE" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            ''|'#'*) continue ;;
        esac
        name=${line%%=*}
        value=${line#*=}
        if [[ "$name" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
            export "$name=$value"
        fi
    done < "$ENV_FILE"
fi


if [ "$#" -eq 0 ]; then
    CAMERA_NUMBER=1
    echo "No camera number given. Using Camera 1"
elif [ "$#" -eq 1 ] && [[ "$1" =~ ^[12]$ ]]; then
    CAMERA_NUMBER=$1
    echo "Using Camera $CAMERA_NUMBER"
else
    echo "Usage: $0 [1|2]" >&2
    exit 2
fi

# Newer .env files store the complete RTSP URL in RTSP_CAM1/RTSP_CAM2.
# Keep compatibility with the former CAMERA1_URL/CAMERA2_URL variables.
if [ "$CAMERA_NUMBER" -eq 1 ]; then
    CAMERA_URL=${RTSP_CAM1:-${CAMERA1_URL:-}}
else
    CAMERA_URL=${RTSP_CAM2:-${CAMERA2_URL:-}}
fi

if [ -z "$CAMERA_URL" ]; then
    echo "Missing RTSP_CAM${CAMERA_NUMBER} (or legacy CAMERA${CAMERA_NUMBER}_URL) in $ENV_FILE" >&2
    exit 1
fi

DT=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="$DATADIR/orig/pigtracking/$DT"
mkdir -p "$OUTPUT_DIR" || exit 1
cd "$OUTPUT_DIR" || exit 1
echo "output dir:"
pwd

## mkdir -p ~/mnt/biomedical/orig/pigtracking/$DT
## cd ~/mnt/biomedical/orig/pigtracking/$DT

#-D 1 # Quit if no packets for 1 second or more
#-c   # Continuously record, after completion of -d timeframe
#-B 10000000 # Input buffer of 10 MB
#-b 10000000 # Output buffer 10MB (to file)
#-q   # Produce files in QuickTime format
#-4   # .mp4 format
#-Q   # Display QOS statistics
#-F cam_eight  # Prefix output filenames with this text
#-d 28800      # Run openRTSP this many seconds
#-P 900        # Start a new output file every -P seconds
#-t            # Request camera end stream over TCP, not UDP
#-u admin 123456  # Username and password expected by camer
#openRTSP -D 1 -c -B 10000000 -b 10000000 -4 -Q -F cam$CAMERA_NUMBER_$DT -d 28800 -P 600 -t -u CAM_USER CAM_PASSWORD rtsp://IPADRESS:PORT
OPENRTSP_ARGS=(-D 1 -c -B 10000000 -b 10000000 -4 -Q -F "${DT}_cam${CAMERA_NUMBER}" -d 28800 -P 300 -t)
if [ -n "${CAMERA_USER:-}" ] || [ -n "${CAMERA_PASS:-}" ]; then
    OPENRTSP_ARGS+=(-u "${CAMERA_USER:-}" "${CAMERA_PASS:-}")
fi
openRTSP "${OPENRTSP_ARGS[@]}" "$CAMERA_URL"
