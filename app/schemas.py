from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional
from datetime import datetime

# Input schema for submitting a URL
class SubmitUrlRequest(BaseModel):
    url: HttpUrl

# Base schema for restaurant data
class RestaurantBase(BaseModel):
    id: int
    name: str
    location: Optional[str] = None
    source_url: Optional[str] = None
    favourited: bool = False
    visited: bool = False
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

# Schema for creating a restaurant (used internally by services/tasks)
class RestaurantCreate(RestaurantBase):
    pass

# Output schema for retrieving a restaurant
class RestaurantOut(RestaurantBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Response after successfully QUEUING a URL
class SubmitUrlResponse(BaseModel):
    message: str
    task_id: str 

# Schema for checking task status ---
class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None 