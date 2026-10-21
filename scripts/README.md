# Install Open RTSP

```bash
echo "deb http://archive.ubuntu.com/ubuntu/ focal main restricted universe multiverse" | sudo tee -a /etc/apt/sources.list
sudo apt-get update
sudo apt-get install livemedia-utils
```

## Export and synchronize tracking data

Export the last 24 hours of quarter-hour activity data and preview images:

```bash
./scripts/export_pigtracking_activity.sh
```

Choose a duration or an explicit time range:

```bash
./scripts/export_pigtracking_activity.sh --last-hours 6
./scripts/export_pigtracking_activity.sh --since 2026-10-20T08:00:00+02:00 --until 2026-10-21T08:00:00+02:00
```

Exports are written below `pigtracking/exports/`. Synchronize videos and exports together with:

```bash
./scripts/sync_pigtracking.sh --dry-run
./scripts/sync_pigtracking.sh
```
