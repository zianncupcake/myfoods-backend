from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional
from datetime import datetime

# --- Item Schemas ---
# 1. Base Schema: Common attributes
class ItemBase(BaseModel):
    source_url: Optional[HttpUrl] = None
    image_url: Optional[HttpUrl] = None
    notes: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    creator: Optional[str] = None

# 2. Create Schema: Attributes required/allowed on creation
class ItemCreate(ItemBase):
    user_id: int 

# 3. Update Schema: Attributes allowed on update (alls optional for PATCH)
class ItemUpdate(BaseModel): 
    source_url: Optional[HttpUrl] = None
    image_url: Optional[HttpUrl] = None
    notes: Optional[str] = None
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    creator: Optional[str] = None

# 4. Read Schema (or "Item" schema): Attributes returned from the API
class Item(ItemBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True, 
    }

# Optional: A schema for a list of items (if you need to return lists with metadata)
# class ItemList(BaseModel):
#     items: List[Item]
#     total: int
#     # limit: int
#     # offset: int

# --- User Schemas ---

# 1. Base Schema for User: Common attributes
class UserBase(BaseModel):
    username: str 

# 2. Create Schema for User: Attributes required for creation
class UserCreate(UserBase):
    password: str  # Password will be received in plain text, HASH IT before saving!

# 3. Update Schema for User: Attributes allowed on update
class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None # If allowing password updates, HASH IT

# 4. Read Schema for User: Attributes returned from the API (NEVER include password)
class User(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime
    items: List[Item] = []

    model_config = {
        "from_attributes": True,
    }

class SubmitUrlRequest(BaseModel):
    url: HttpUrl

class SubmitUrlResponse(BaseModel):
    message: str
    task_id: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None 

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
