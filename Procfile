web: gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --preload
worker: celery -A app.worker.celery_app worker --loglevel=info
