from fastapi import FastAPI, HTTPException, Query, status, WebSocket, WebSocketDisconnect, APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List, Optional, Annotated
import logging
import asyncio

from . import schemas, crud, security
from .db import lifespan 
from .worker.tasks import process_url_task 
from .worker.celery_app import celery 
from celery.result import AsyncResult
from .models import User as UserModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("uvicorn")

app = FastAPI(
    title="MyFoods Backend API (Async)",
    description="API to asynchronously process social media URLs and store item data.",
    version="0.2.0",
    lifespan=lifespan
)

users_router = APIRouter(prefix="/users", tags=["Users"])
items_router = APIRouter(prefix="/items", tags=["Items"])
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

@auth_router.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = await crud.authenticate_user(username=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = security.create_access_token(
        data={"sub": user.username} 
    )
    return {"access_token": access_token, "token_type": "bearer"}

@users_router.post("/", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
async def create_new_user(user_in: schemas.UserCreate):
    db_user = await crud.get_user_by_username(username=user_in.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    created_user = await crud.create_user(user_data=user_in)
    if not created_user:
        raise HTTPException(status_code=500, detail="Could not create user")
    
    await created_user.fetch_related('items')
    return created_user

@users_router.get("/me", response_model=schemas.User)
async def get_current_active_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserModel:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    username = security.decode_token_for_username(token, credentials_exception)
    if username is None: 
        raise credentials_exception
    user = await crud.get_user_by_username(username=username)
    if user is None:
        raise credentials_exception
    await user.fetch_related('items')
    return user

@users_router.get("/{user_id}", response_model=schemas.User)
async def read_user(user_id: int):
    db_user = await crud.get_user_by_id(user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@users_router.get("/{user_id}/items", response_model=List[schemas.Item])
async def read_items_for_user(user_id: int):
    db_user = await crud.get_user_by_id(user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    items = await crud.get_user_items(user_id=user_id)
    return items

@users_router.put("/{user_id}", response_model=schemas.User)
async def update_existing_user(user_id: int, user_in: schemas.UserUpdate):
    updated_user = await crud.update_user(user_id=user_id, user_data=user_in)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found or update failed")
    
    await updated_user.fetch_related('items')
    return updated_user

@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(user_id: int):
    deleted = await crud.delete_user(user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return None 

@items_router.post("/", response_model=schemas.Item, status_code=status.HTTP_201_CREATED)
async def create_new_item(item_in: schemas.ItemCreate):
    owner = await crud.get_user_by_id(item_in.user_id)
    if not owner:
        raise HTTPException(status_code=404, detail=f"Owner user with id {item_in.user_id} not found.")
    return await crud.create_item(item_data=item_in)

@items_router.get("/{item_id}", response_model=schemas.Item)
async def read_item_by_id(item_id: int):
    db_item = await crud.get_item_by_id(item_id=item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return db_item

@items_router.put("/{item_id}", response_model=schemas.Item)
async def update_existing_item(item_id: int, item_in: schemas.ItemUpdate):
    db_item = await crud.get_item_by_id(item_id) 
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    updated_item = await crud.update_item(
        item_id=item_id, item_data=item_in, owner_id=db_item.user_id 
    )
    if not updated_item:
        raise HTTPException(status_code=404, detail="Item not found or update failed")
    return updated_item

@items_router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_item(item_id: int):
    db_item = await crud.get_item_by_id(item_id) 
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    deleted = await crud.delete_item(item_id=item_id, owner_id=db_item.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found or delete failed")
    return None

# --- Include Routers in the main app ---
app.include_router(users_router)
app.include_router(items_router)
app.include_router(auth_router)

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

@app.websocket("/ws/task_status/{task_id}")
async def websocket_task_status(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for a client to connect and receive updates for a specific task.
    The server will poll the Celery task status and push the final result to the client.
    """
    await websocket.accept()
    log.info(f"WebSocket connected: client {websocket.client}, task_id: {task_id}")

    try:
        while True:
            task_result = AsyncResult(task_id) 

            current_status = task_result.status
            log.info(f"WS Polling for {task_id}: Status - {current_status}")

            payload = {
                "task_id": task_id,
                "status": current_status,
                "result": None
            }

            if task_result.successful():
                payload["result"] = task_result.get() 
                await websocket.send_json(payload)
                log.info(f"WS: Sent SUCCESS for task {task_id} to client {websocket.client}.")
                break  
            elif task_result.failed():
                payload["result"] = {
                    "error": "Task processing failed.",
                    "traceback": str(task_result.traceback) 
                }
                await websocket.send_json(payload)
                log.info(f"WS: Sent FAILURE for task {task_id} to client {websocket.client}.")
                break  
            elif current_status in ["PENDING", "STARTED", "RETRY"]:
                # Task is still processing. Optionally send an update or just wait.
                # For this "easiest" version, we only send the final state.
                pass
            else:
                log.warning(f"WS: Task {task_id} in unexpected state: {current_status} for client {websocket.client}.")
                payload["status"] = "UNKNOWN_STATUS"
                payload["result"] = {"error": f"Task is in an unexpected state: {current_status}."}
                await websocket.send_json(payload)
                break 

            # Wait for a short period before checking the status again
            await asyncio.sleep(2) 

    except WebSocketDisconnect:
        log.info(f"WebSocket disconnected: client {websocket.client}, task_id: {task_id}")
    except Exception as e:
        log.error(f"Error in WebSocket for task_id {task_id}, client {websocket.client}: {e}", exc_info=True)
        # Attempt to send an error to the client if the connection is still open
        try:
            await websocket.send_json({
                "task_id": task_id,
                "status": "ERROR",
                "result": {"error": "WebSocket communication error", "detail": str(e)}
            })
        except Exception:
            log.error(f"Could not send error to disconnected client {websocket.client} for task {task_id}")
    finally:
        # Ensure the WebSocket is closed if it hasn't been already.
        # FastAPI handles closing on disconnect or if the handler finishes.
        log.info(f"WebSocket connection handling finished for task_id: {task_id}, client: {websocket.client}")
