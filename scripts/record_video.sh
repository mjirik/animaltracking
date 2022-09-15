#!/bin/bash

# sudo apt-get install sshfs livemedia-utils

mkdir -p ~/mnt/biomedical
sshfs mjirik@storage-plzen4.kky.zcu.cz:/data-ntis/projects/korpusy_cv/biomedical ~/mnt/biomedical

