# Animal tracking
 
## Prerequisities

* Docker
* Conda environment `pigtracking` for local non-Docker run

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
2. PEN worker that reads the latest camera snapshots, crops PEN images, runs RF-DETR detection, and writes dashboard images

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
