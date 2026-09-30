# Animal tracking
 
## Prerequisities

* Docker
* Conda environment `pigtracking` for local non-Docker run

## Model weights

Trained weights are distributed separately from the Git repository as release
assets. Download `pigtracking_rfdetr_best.pth` from the matching GitHub release
and place it in `models/`. Keep the small class-map and metadata JSON files from
this repository next to it:

```text
models/
├── pigtracking_rfdetr_best.pth
├── pigtracking_rfdetr_best.classes.json
└── pigtracking_rfdetr_best.metadata.json
```

For release `v0.0.1`, verify the downloaded checkpoint with:

```bash
echo "6e836d9db8da992b0ca7f1383ec348848eb51bf51f9523414e6476d910992e0e  models/pigtracking_rfdetr_best.pth" | sha256sum --check
```

The generic RF-DETR pretraining files (`rf-detr-nano.pth` and
`rf-detr-medium.pth`) are not application release artifacts; RF-DETR can fetch
its own pretrained weights when they are needed for training.

## Run application for debug

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

### Migrations

```bash
#docker compose exec webapp python manage.py migrate
docker compose exec webapp bash
python manage.py makemigrations
python manage.py migrate
```



## Run application for production

```bash
docker compose -f docker-compose.yml up --build -d
```

## Run PEN dashboard without Docker

The current PEN dashboard uses two long-running processes:

1. Django web server
2. PEN worker that reads RTSP cameras directly, crops PEN images, runs RF-DETR detection, and writes dashboard images

Before the first run:

```bash
conda run -n pigtracking python src/animaltracking/manage.py migrate
```

Manual start in two terminals:

```bash
conda run --no-capture-output -n pigtracking python -u src/animaltracking/manage.py runserver 0.0.0.0:8000
```

```bash
conda run --no-capture-output -n pigtracking python -u src/animaltracking/manage.py run_pen_worker --device cuda:0 --threshold 0.25
```

Optional timeout for one RTSP capture:

```bash
conda run --no-capture-output -n pigtracking python -u src/animaltracking/manage.py run_pen_worker --device cuda:0 --threshold 0.25 --capture-timeout 30
```

Dashboard URL:

```text
http://127.0.0.1:8000/antra/
http://localhost:8000/antra/
http://100.124.208.94:8000/antra/
```

The allowed hosts are read from `.env` via:

```env
ANTRA_ALLOWED_HOSTS=127.0.0.1,localhost,100.124.208.94
```

### Start helper script

To start both processes in the background with logs and PID files:

```bash
./scripts/start_pen_dashboard.sh
```

Logs are written to:

```text
logs/pigtracking_dashboard/web.log
logs/pigtracking_dashboard/worker.log
```

For live log monitoring:

```bash
tail -f logs/pigtracking_dashboard/web.log
tail -f logs/pigtracking_dashboard/worker.log
```

To stop both processes:

```bash
./scripts/stop_pen_dashboard.sh
```
