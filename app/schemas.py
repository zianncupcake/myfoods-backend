from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional
from datetime import datetime

# Input schema for submitting a URL
class SubmitUrlRequest(BaseModel):
    url: HttpUrl

# # Base schema for restaurant data
# class RestaurantBase(BaseModel):
#     id: int
#     name: str
#     location: Optional[str] = None
#     source_url: Optional[str] = None
#     favourited: bool = False
#     visited: bool = False
#     tags: List[str] = Field(default_factory=list)
#     created_at: datetime
#     updated_at: datetime

# # Schema for creating a restaurant (used internally by services/tasks)
# class RestaurantCreate(RestaurantBase):
#     pass

# # Output schema for retrieving a restaurant
# class RestaurantOut(RestaurantBase):
#     id: int
#     created_at: datetime
#     updated_at: datetime

#     class Config:
#         from_attributes = True

# # Response after successfully QUEUING a URL
# class SubmitUrlResponse(BaseModel):
#     message: str
#     task_id: str 

# # Schema for checking task status ---
# class TaskStatusResponse(BaseModel):
#     task_id: str
#     status: str
#     result: Optional[dict] = None 

# from pydantic import BaseModel, HttpUrl, Field, UUID4
# from typing import List, Optional
# from datetime import datetime
# import uuid # For generating UUIDs

# # --- Input Schemas ---
# class SubmitUrlRequest(BaseModel):
#     url: HttpUrl # Assuming you still want to submit URLs

# # --- Item Schemas ---
# class ItemBase(BaseModel):
#     source_url: Optional[HttpUrl] = None # Assuming source_url is still an HttpUrl
#     title: Optional[str] = None
#     notes: Optional[str] = None
#     categories: List[str] = Field(default_factory=list)
#     tags: List[str] = Field(default_factory=list)
#     creator: Optional[str] = None # Or make it non-optional if always required
#     # You might want to add favourited, visited, etc. if still needed
#     # favourited: bool = Field(default=False)
#     # visited: bool = Field(default=False)


# class ItemCreate(ItemBase):
#     # Fields that are required on creation or have defaults handled by the DB/server
#     # If title is mandatory on creation:
#     title: str # Making title mandatory for creation example

# class ItemUpdate(ItemBase):
#     title: Optional[str] = None
#     source_url: Optional[HttpUrl] = None
#     notes: Optional[str] = None
#     categories: Optional[List[str]] = None
#     tags: Optional[List[str]] = None
#     creator: Optional[str] = None
#     # favourited: Optional[bool] = None
#     # visited: Optional[bool] = None

# class ItemOut(ItemBase):
#     id: int
#     created_at: datetime
#     updated_at: datetime

#     class Config:
#         from_attributes = True


from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, HttpUrl, Field, EmailStr # Added EmailStr

# --- Item Schemas ---
# 1. Base Schema: Common attributes
class ItemBase(BaseModel):
    title: Optional[str] = None
    source_url: Optional[HttpUrl] = None
    notes: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    creator: Optional[str] = None # Could also be a foreign key to a User ID later

# 2. Create Schema: Attributes required/allowed on creation
class ItemCreate(ItemBase):
    title: str # Mandatory
    source_url: HttpUrl # Mandatory
    # Other fields from ItemBase are optional with their defaults

# 3. Update Schema: Attributes allowed on update (all optional for PATCH)
class ItemUpdate(BaseModel): # Inherits BaseModel directly for explicit optionality
    title: Optional[str] = None
    source_url: Optional[HttpUrl] = None
    notes: Optional[str] = None
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    creator: Optional[str] = None

# 4. Read Schema (or "Item" schema): Attributes returned from the API
class Item(ItemBase):
    id: int
    created_at: datetime
    updated_at: datetime

    # Pydantic V2 configuration
    model_config = {
        "from_attributes": True, # Allows Pydantic to read data from ORM model attributes
    }

    # For Pydantic V1, you would use:
    # class Config:
    #     orm_mode = True

# Optional: A schema for a list of items (if you need to return lists with metadata)
class ItemList(BaseModel):
    items: List[Item]
    total: int
    # limit: int
    # offset: int

# --- User Schemas ---

# 1. Base Schema for User: Common attributes
class UserBase(BaseModel):
    phone_number: str # Making phone_number a primary identifier
    # You might want to add a username field if phone_number isn't unique or for login
    # username: Optional[str] = None

# 2. Create Schema for User: Attributes required for creation
class UserCreate(UserBase):
    phone_number: str # Ensure it's provided on creation
    password: str  # Password will be received in plain text, HASH IT before saving!
    # email: EmailStr # Make email mandatory on creation if desired

# 3. Update Schema for User: Attributes allowed on update
class UserUpdate(BaseModel):
    password: Optional[str] = None # If allowing password updates, HASH IT

# 4. Read Schema for User: Attributes returned from the API (NEVER include password)
class User(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime
    items: List[Item] = [] # Example of a relationship: items created by this user

    # Pydantic V2 configuration
    model_config = {
        "from_attributes": True,
    }
    # For Pydantic V1:
    # class Config:
    #     orm_mode = True

# Optional: A schema for a list of users
class UserList(BaseModel):
    users: List[User]
    total: int
    # limit: int
    # offset: int
class SubmitUrlResponse(BaseModel):
    message: str
    task_id: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None 