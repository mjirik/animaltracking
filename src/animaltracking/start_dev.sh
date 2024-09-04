#!/bin/bash

# prepare django
# migrations should be prepared from the outside of the docker and should be commited to github
# python manage.py makemigrations --noinput --verbosity 2

python manage.py migrate --noinput --verbosity 2
python manage.py collectstatic --noinput --verbosity 2

python manage.py rqworker default
#python manage.py rqworker high default low
# start "local" celery worker
# C_FORCE_ROOT=false celery -A caidapp.celery_app worker --pool threads --loglevel info &

# start django
python manage.py runserver 0.0.0.0:8080

#uvicorn animaltracking.asgi:application \
#    --host 0.0.0.0 \
#    --port 8080 \
#    --log-config logging.yaml \
#    --log-level debug\
#    --reload