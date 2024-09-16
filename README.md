# Animal tracking
 
## Prerequisities

* Docker

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