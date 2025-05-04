from celery import Celery
from app.config import settings 
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

log.info(f"Initializing Celery with broker: {settings.redis_url}")

# Create Celery instance
# The first argument is the name of the current module (__name__)
# The 'broker' and 'backend' arguments specify the Redis connection URLs
celery = Celery(
    __name__,
    broker=settings.redis_url,
    backend=settings.redis_url 
)

# Optional Celery configuration
celery.conf.update(
    task_track_started=True,            
    broker_connection_retry_on_startup=True, 
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
)

# Automatically discover tasks in the 'tasks.py' file within this 'worker' package
# It looks for tasks defined in modules listed in the 'include' list.
celery.autodiscover_tasks(['app.worker'])

log.info("Celery instance configured and ready.")