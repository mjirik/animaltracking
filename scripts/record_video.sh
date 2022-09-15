#!/bin/bash

# sudo apt-get install sshfs livemedia-utils

mkdir -p ~/mnt/biomedical
sshfs mjirik@storage-plzen4.kky.zcu.cz:/data-ntis/projects/korpusy_cv/biomedical ~/mnt/biomedical



DT=$(date +%Y%m%d_%H%M%S)
mkdir -p ~/mnt/biomedical/orig/pigtracking/$DT
cd ~/mnt/biomedical/orig/pigtracking/$DT
openRTSP -D 1 -c -B 10000000 -b 10000000 -4 -Q -F cam1 -d 28800 -P 600 -t -u User1 Zverinec rtsp://195.113.130.63:2554
