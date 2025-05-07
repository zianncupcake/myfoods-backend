release: PLAYWRIGHT_BROWSERS_PATH=0 python -m playwright install chromium
web: PLAYWRIGHT_BROWSERS_PATH=0 playwright install && gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --preload
worker: celery -A app.worker.celery_app worker --loglevel=info
