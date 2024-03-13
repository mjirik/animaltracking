# Animal tracking
 
## Prerequisities

* Docker

## Run application for debug

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

## Run application for production

```bash
docker compose -f docker-compose.yml up --build -d
```