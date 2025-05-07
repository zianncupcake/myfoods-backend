release: python -m playwright install chromium
web: playwright install && gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --preload
worker: celery -A app.worker.celery_app worker --loglevel=info
