from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.core.cache import get_cache
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.core.rate_limit import get_rate_limit_decorator
from app.deps.supabase import get_supabase_client
from app.models.pantry import (
    PantryItem,
    PantryItemUpsert,
    PantryItemUpsertResponse,
    PantryItemsBulkCreateRequest,
    PantryItemsBulkCreateResponse,
)
from app.services.auth import get_current_household_id, get_current_user_id
from app.services.pantry_service import PantryService

logger = get_logger(__name__)
router: APIRouter = APIRouter(prefix="/pantry", tags=["pantry"])
rate_limit = get_rate_limit_decorator()


def _invalidate_household_cache(household_id: UUID) -> None:
    """Invalidate cache for household-scoped queries."""
    cache = get_cache()
    cache.delete(f"pantry:household:{household_id}")


def _invalidate_user_cache(household_id: UUID, user_id: UUID) -> None:
    """Invalidate cache for user-scoped queries."""
    cache = get_cache()
    cache.delete(f"pantry:user:{household_id}:{user_id}")


def _get_cached_household_items(household_id: UUID) -> list[PantryItem] | None:
    """Get cached household items or None if not cached."""
    cache = get_cache()
    cache_key = f"pantry:household:{household_id}"
    return cache.get(cache_key)


def _set_cached_household_items(household_id: UUID, items: list[PantryItem]) -> None:
    """Cache household items with 60s TTL."""
    cache = get_cache()
    cache_key = f"pantry:household:{household_id}"
    cache.set(cache_key, items, ttl_seconds=60)


def _get_cached_user_items(household_id: UUID, user_id: UUID) -> list[PantryItem] | None:
    """Get cached user items or None if not cached."""
    cache = get_cache()
    cache_key = f"pantry:user:{household_id}:{user_id}"
    return cache.get(cache_key)


def _set_cached_user_items(household_id: UUID, user_id: UUID, items: list[PantryItem]) -> None:
    """Cache user items with 60s TTL."""
    cache = get_cache()
    cache_key = f"pantry:user:{household_id}:{user_id}"
    cache.set(cache_key, items, ttl_seconds=60)

def get_pantry_service(supabase: Client = Depends(get_supabase_client)) -> PantryService:
    """
    Dependency injector for PantryService.
    Returns a PantryService instance using the given Supabase client.
    """
    return PantryService(supabase)

@rate_limit
async def add_single_pantry_item(
    *,
    pantry_item: PantryItemUpsert,
    household_id: UUID = Depends(get_current_household_id),
    user_id: UUID = Depends(get_current_user_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> PantryItemUpsertResponse:
    """
    Add a single item to the user's household pantry.
    - Validates and persists an individual PantryItemUpsert.
    - Returns result model or raises HTTP 500 if insert fails.
    - Invalidates relevant caches after successful insert.
    """
    result = await pantry_service.add_pantry_item_single(pantry_item, household_id, user_id)
    if result is None:
        logger.error("Failed to add pantry item", extra={"household_id": str(household_id), "user_id": str(user_id)})
        raise AppError("Failed to add pantry item", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    _invalidate_household_cache(household_id)
    _invalidate_user_cache(household_id, user_id)
    
    logger.info("Pantry item added", extra={"item_id": getattr(result, "id", None), "household_id": str(household_id)})
    return result

@rate_limit
async def add_multiple_pantry_items(
    *,
    pantry_items: PantryItemsBulkCreateRequest,
    household_id: UUID = Depends(get_current_household_id),
    user_id: UUID = Depends(get_current_user_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> PantryItemsBulkCreateResponse:
    """
    Add multiple pantry items in a single request for the user's household.
    - Ensures items list is not empty.
    - Uses pantry_service to perform a batch add.
    - Raises HTTP 400 if no items, HTTP 500 if failed to add.
    - Invalidates relevant caches after successful bulk insert.
    """
    if not pantry_items.items:
        logger.error("Bulk add: no pantry items provided")
        raise AppError("No pantry items provided", status_code=status.HTTP_400_BAD_REQUEST)
    result = await pantry_service.add_pantry_item_bulk(pantry_items.items, household_id, user_id)
    if result is None:
        logger.error("Bulk pantry add failed", extra={"household_id": str(household_id), "count": len(pantry_items.items)})
        raise AppError("Bulk pantry add failed", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    _invalidate_household_cache(household_id)
    _invalidate_user_cache(household_id, user_id)
    
    logger.info("Bulk pantry items added", extra={"household_id": str(household_id), "successful": result.successful})
    return result

async def get_all_pantry_items(
    *,
    household_id: UUID = Depends(get_current_household_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> list[PantryItem]:
    """
    Fetch all pantry items belonging to the current user's household.
    - Returns an empty list if query fails or no items found.
    - Results are cached for 60 seconds.
    """
    cached_items = _get_cached_household_items(household_id)
    if cached_items is not None:
        logger.debug("Cache hit for household pantry items", extra={"household_id": str(household_id)})
        return cached_items
    
    items = await pantry_service.get_household_pantry_items(household_id)
    if items is None:
        logger.info("Get household pantry items returned none", extra={"household_id": str(household_id)})
        return []
    
    _set_cached_household_items(household_id, items)
    logger.info("Fetched household pantry items", extra={"household_id": str(household_id), "count": len(items)})
    return items

async def get_my_pantry_items(
    *,
    user_id: UUID = Depends(get_current_user_id),
    household_id: UUID = Depends(get_current_household_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> list[PantryItem]:
    """
    Fetch pantry items for the current user in their household.
    - Delegates to pantry_service method to scope by user.
    - Returns an empty list if none are found or operation fails.
    - Results are cached for 60 seconds.
    """
    cached_items = _get_cached_user_items(household_id, user_id)
    if cached_items is not None:
        logger.debug("Cache hit for user pantry items", extra={"household_id": str(household_id), "user_id": str(user_id)})
        return cached_items
    
    items = await pantry_service.get_my_pantry_items(household_id, user_id)
    if items is None:
        logger.info("Get my pantry items returned none", extra={"household_id": str(household_id), "user_id": str(user_id)})
        return []
    
    _set_cached_user_items(household_id, user_id, items)
    logger.info("Fetched my pantry items", extra={"household_id": str(household_id), "user_id": str(user_id), "count": len(items)})
    return items

@rate_limit
async def update_pantry_item(
    *,
    pantry_item: PantryItemUpsert,
    household_id: UUID = Depends(get_current_household_id),
    user_id: UUID = Depends(get_current_user_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> PantryItemUpsertResponse:
    """
    Update an existing pantry item.
    - Raises HTTP 404 if the item doesn't exist or cannot be updated (e.g., permissions, not found).
    - Otherwise returns updated PantryItemUpsertResponse.
    - Invalidates relevant caches after successful update.
    """
    result = await pantry_service.update_pantry_item(pantry_item, household_id, user_id)
    if result is None:
        logger.error("Pantry item update failed (not found or forbidden)", extra={"household_id": str(household_id), "user_id": str(user_id)})
        raise AppError("Pantry item not found or could not be updated", status_code=status.HTTP_404_NOT_FOUND)
    
    _invalidate_household_cache(household_id)
    _invalidate_user_cache(household_id, user_id)
    
    logger.info("Pantry item updated", extra={"item_id": getattr(pantry_item, "id", None), "household_id": str(household_id)})
    return result

@rate_limit
async def delete_pantry_item(
    *,
    item_id: UUID,
    household_id: UUID = Depends(get_current_household_id),
    user_id: UUID = Depends(get_current_user_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> PantryItemUpsertResponse:
    """
    Delete a pantry item identified by item_id in the user's household.
    - Returns deleted item details or raises HTTP 404 if not found.
    - Invalidates relevant caches after successful deletion.
    """
    result = await pantry_service.delete_pantry_item(item_id, household_id, user_id)
    if result is None:
        logger.error("Pantry item delete failed (not found)", extra={"item_id": str(item_id), "household_id": str(household_id)})
        raise AppError("Pantry item not found for deletion", status_code=status.HTTP_404_NOT_FOUND)
    
    _invalidate_household_cache(household_id)
    _invalidate_user_cache(household_id, user_id)
    
    logger.info("Pantry item deleted", extra={"item_id": str(item_id), "household_id": str(household_id)})
    return result

router.post(
    "/add-item",
    response_model=PantryItemUpsertResponse,
)(add_single_pantry_item)
router.post(
    "/add_item",
    response_model=PantryItemUpsertResponse,
    include_in_schema=False,
)(add_single_pantry_item)

router.post(
    "/bulk-add",
    response_model=PantryItemsBulkCreateResponse,
)(add_multiple_pantry_items)
router.post(
    "/bulk_add",
    response_model=PantryItemsBulkCreateResponse,
    include_in_schema=False,
)(add_multiple_pantry_items)

router.get(
    "/household-items",
    response_model=list[PantryItem],
)(get_all_pantry_items)
router.get(
    "/get_household_items",
    response_model=list[PantryItem],
    include_in_schema=False,
)(get_all_pantry_items)

router.get(
    "/my-items",
    response_model=list[PantryItem],
)(get_my_pantry_items)
router.get(
    "/get_my_items",
    response_model=list[PantryItem],
    include_in_schema=False,
)(get_my_pantry_items)

router.put(
    "/update-item",
    response_model=PantryItemUpsertResponse,
)(update_pantry_item)
router.put(
    "/update_item",
    response_model=PantryItemUpsertResponse,
    include_in_schema=False,
)(update_pantry_item)

router.delete(
    "/delete-item",
    response_model=PantryItemUpsertResponse,
)(delete_pantry_item)
router.delete(
    "/delete_item",
    response_model=PantryItemUpsertResponse,
    include_in_schema=False,
)(delete_pantry_item)

__all__ = [
    "router",
    "add_single_pantry_item",
    "add_multiple_pantry_items",
    "get_all_pantry_items",
    "get_my_pantry_items",
    "update_pantry_item",
    "delete_pantry_item",
]
