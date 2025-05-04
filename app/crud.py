from typing import List, Optional
from .models import Restaurant
from .schemas import RestaurantOut
from tortoise.exceptions import DoesNotExist
import logging

log = logging.getLogger("uvicorn") 

async def get_restaurant(restaurant_id: int) -> Optional[RestaurantOut]:
    """Fetch a single restaurant by its ID."""
    try:
        restaurant = await Restaurant.get(id=restaurant_id)
        return RestaurantOut.model_validate(restaurant)
    except DoesNotExist:
        log.warning(f"Restaurant with id {restaurant_id} not found.")
        return None
    except Exception as e:
        log.error(f"Error fetching restaurant {restaurant_id}: {e}", exc_info=True)
        return None

async def get_restaurants(skip: int = 0, limit: int = 10) -> List[RestaurantOut]:
    """Fetch a list of restaurants with pagination."""
    try:
        restaurants = await Restaurant.all().offset(skip).limit(limit).order_by('-created_at')
        return [RestaurantOut.model_validate(r) for r in restaurants]
    except Exception as e:
        log.error(f"Error fetching restaurants list (skip={skip}, limit={limit}): {e}", exc_info=True)
        return []

# async def get_restaurant_by_source_url(url: str) -> Optional[Restaurant]:
#     """Fetch a single restaurant Tortoise model by source_url (internal use)."""
#     try:
#         # Use get_or_none to avoid DoesNotExist exception if not found
#         return await Restaurant.get_or_none(source_url=url)
#     except Exception as e:
#         log.error(f"Error fetching restaurant by source URL {url}: {e}", exc_info=True)
#         return None

async def create_or_update_restaurant(source_url: str, data: dict) -> Optional[Restaurant]:
    """Creates a new restaurant or updates an existing one based on source_url."""
    # Note: This function now expects to be called within a context
    # where Tortoise ORM is already initialized (e.g., inside the Celery task)
    try:
        existing_restaurant = await get_restaurant_by_source_url(source_url)

        if existing_restaurant:
            log.info(f"Updating existing restaurant from {source_url} (ID: {existing_restaurant.id})")
            # Perform the update
            await Restaurant.filter(id=existing_restaurant.id).update(**data)
            # Fetch the updated instance
            updated_restaurant = await Restaurant.get(id=existing_restaurant.id)
            return updated_restaurant
        else:
            log.info(f"Creating new restaurant from {source_url}")
            new_restaurant = await Restaurant.create(source_url=source_url, **data)
            return new_restaurant
    except Exception as e:
        log.error(f"Error creating/updating restaurant for {source_url}: {e}", exc_info=True)
        return None