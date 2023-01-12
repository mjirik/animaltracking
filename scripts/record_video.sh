#!/bin/bash

# echo "deb http://archive.ubuntu.com/ubuntu/ focal main restricted universe multiverse" | sudo tee -a /etc/apt/sources.list
# sudo apt-get update
# sudo apt-get install sshfs livemedia-utils

mkdir -p ~/mnt/biomedical
sshfs mjirik@storage-plzen4.kky.zcu.cz:/data-ntis/projects/korpusy_cv/biomedical ~/mnt/biomedical

# create .vim file with keys: $CAMERA_USER $CAMERA_PASS $CAMERA_URL
export $(grep -v '^#' .env | xargs -d '\n')

if [ "$#" -ne 1 ]; then
    export CAMERA_URL=$CAMERA1_URL
    echo "No camera number given. Using Camera 1"
else
    if [ "$1" -eq 2 ]; then
        export CAMERA_URL=$CAMERA2_URL
        echo "Using Camera 2"
    else
        export CAMERA_URL=$CAMERA1_URL
        echo "Using Camera 1"
    fi
fi

DT=$(date +%Y%m%d_%H%M%S)
mkdir -p ~/mnt/biomedical/orig/pigtracking/$DT
cd ~/mnt/biomedical/orig/pigtracking/$DT
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
#openRTSP -D 1 -c -B 10000000 -b 10000000 -4 -Q -F cam1 -d 28800 -P 600 -t -u CAM_USER CAM_PASSWORD rtsp://IPADRESS:PORT
openRTSP -D 1 -c -B 10000000 -b 10000000 -4 -Q -F cam1 -d 28800 -P 600 -t -u $CAMERA_USER $CAMERA_PASS $CAMERA_URL
