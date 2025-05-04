from fastapi import FastAPI, HTTPException, Depends, Query, status
from typing import List, Optional
import logging

from . import schemas, crud
from .db import lifespan 
from .worker.tasks import process_url_task 
from .worker.celery_app import celery 

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("uvicorn")

app = FastAPI(
    title="MyFoods Backend API (Async)",
    description="API to asynchronously process social media URLs and store restaurant data.",
    version="0.2.0",
    lifespan=lifespan
)

# --- API Endpoints ---
@app.get("/", tags=["General"])
async def read_root():
    """Provides a simple welcome message."""
    log.info("Root endpoint accessed.")
    return {"message": "Welcome to the MyFoods Backend API! (Async Tasks Enabled)"}


@app.post("/submit_url",
          response_model=schemas.SubmitUrlResponse,
          status_code=status.HTTP_202_ACCEPTED,
          tags=["Restaurants"],
          summary="Submit URL for Background Processing")
async def submit_social_media_url_async(submit_request: schemas.SubmitUrlRequest):
    """
    Accepts a tiktok URL and queues it for background processing using Celery.
    Returns immediately with a task ID.
    """
    url_to_process = str(submit_request.url)
    log.info(f"Received URL submission for background processing: {url_to_process}")

    try:
        # Send the task to Celery queue
        # .delay() is a shortcut for .apply_async()
        task = process_url_task.delay(url_to_process)
        log.info(f"Task {task.id} queued for URL: {url_to_process}")

        return {"message": "URL received and queued for processing.", "task_id": task.id}
    except Exception as e:
        log.error(f"Failed to queue task for {url_to_process}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue URL for processing. Please try again later."
        )


@app.get("/restaurants",
         response_model=List[schemas.RestaurantOut],
         tags=["Restaurants"],
         summary="Get Saved Restaurants")
async def read_restaurants(skip: int = 0, limit: int = Query(default=10, le=100)):
    """
    Retrieve a list of restaurants stored in the database, with pagination.
    """
    log.info(f"Fetching restaurants list: skip={skip}, limit={limit}")
    restaurants = await crud.get_restaurants(skip=skip, limit=limit)
    return restaurants

@app.get("/restaurants/{restaurant_id}",
         response_model=schemas.RestaurantOut,
         tags=["Restaurants"],
         summary="Get Specific Restaurant")
async def read_restaurant(restaurant_id: int):
    """
    Retrieve details for a specific restaurant by its ID.
    """
    log.info(f"Fetching restaurant with id: {restaurant_id}")
    db_restaurant = await crud.get_restaurant(restaurant_id)
    if db_restaurant is None:
        log.warning(f"Restaurant with id {restaurant_id} not found for retrieval.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    return db_restaurant

@app.get("/task_status/{task_id}",
         response_model=schemas.TaskStatusResponse,
         tags=["Tasks"],
         summary="Check Background Task Status")
async def get_task_status(task_id: str):
    """
    Check the status and result of a background task previously submitted.
    Requires the Celery result backend (Redis in this case) to be configured.
    """
    log.info(f"Checking status for task ID: {task_id}")
    task_result = celery.AsyncResult(task_id)

    response = {
        "task_id": task_id,
        "status": task_result.status,
        "result": None
    }

    if task_result.successful():
        response["result"] = task_result.get() 
    elif task_result.failed():
        response["result"] = {"error": "Task failed", "traceback": str(task_result.traceback)}
    # Other statuses: PENDING, STARTED, RETRY

    log.info(f"Task {task_id} status: {task_result.status}")
    return response