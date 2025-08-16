import logging
from typing import List, Optional
from tortoise.exceptions import DoesNotExist, IntegrityError

from .security import get_password_hash, verify_password
from .models import User as UserModel, Item as ItemModel
from .schemas import UserCreate, UserUpdate, ItemCreate, ItemUpdate

log = logging.getLogger("uvicorn") 

async def get_user_by_username(username: str) -> Optional[UserModel]:
    try:
        return await UserModel.get(username=username)
    except DoesNotExist:
        return None

async def get_user_by_id(userId: int) -> Optional[UserModel]:
    try:
        return await UserModel.get(id=userId)
    except DoesNotExist:
        return None

async def create_user(user_data: UserCreate) -> Optional[UserModel]:
    hashed_password = get_password_hash(user_data.password) 
    try:
        user_obj = await UserModel.create(
            username=user_data.username,
            password=hashed_password
        )
        return user_obj
    except IntegrityError:
        return None

async def authenticate_user(username: str, password: str) -> Optional[UserModel]:
    try:
        user = await UserModel.get(username=username)
    except DoesNotExist:
        return None

    if not user: 
        return None
    if not verify_password(password, user.password): 
        return None
    return user

async def update_user(user_id: int, user_data: UserUpdate) -> Optional[UserModel]:
    user = await UserModel.get_or_none(id=user_id) 
    if not user:
        return None

    update_data = user_data.model_dump(exclude_unset=True)

    if "password" in update_data and update_data["password"]:
        hashed_password = get_password_hash(update_data["password"]) 
        user.password = hashed_password
        del update_data["password"]

    for key, value in update_data.items():
        setattr(user, key, value)

    await user.save()
    return user

async def delete_user(user_id: int) -> bool:
    try:
        user = await UserModel.get(id=user_id)
        await user.delete()
        return True
    except DoesNotExist:
        return False

async def create_item(item_data: ItemCreate) -> ItemModel:
    item_obj = await ItemModel.create(**item_data.model_dump())
    return item_obj

async def get_item_by_id(item_id: int) -> Optional[UserModel]:
    try:
        return await ItemModel.get(id=item_id)
    except DoesNotExist:
        return None

async def get_user_items(user_id: int, skip: int = 0, limit: int = 100) -> List[ItemModel]:
    return await ItemModel.filter(user_id=user_id).order_by('-created_at').offset(skip).limit(limit).all()

async def update_item(item_id: int, item_data: ItemUpdate, owner_id: int) -> Optional[ItemModel]:
    try:
        item = await ItemModel.get(id=item_id)
    except DoesNotExist:
        return None

    if item.user_id != owner_id:
        return None # Or raise an exception

    update_data = item_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)
    await item.save()
    return item

async def delete_item(item_id: int, owner_id: int) -> bool:
    try:
        item = await ItemModel.get(id=item_id)
        if item.user_id != owner_id:
            return False
        await item.delete()
        return True
    except DoesNotExist:
        return False
