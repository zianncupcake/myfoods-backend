web: PLAYWRIGHT_BROWSERS_PATH=0 playwright install && gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --preload
worker: PLAYWRIGHT_BROWSERS_PATH=0 playwright install && celery -A app.worker.celery_app worker --loglevel=info
