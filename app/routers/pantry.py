from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from typing import List

from app.deps.supabase import get_supabase_client
from app.services.auth import get_current_household_id, get_current_user_id
from app.services.pantry_service import PantryService
from app.models.pantry import (
    PantryItemUpsert,
    PantryItemUpsertResponse,
    PantryItem,
    PantryItemsBulkCreateRequest,
    PantryItemsBulkCreateResponse,
)
from supabase import Client

# Initialize the APIRouter for pantry-related endpoints,
# with all routes prefixed by '/pantry' and tagged 'pantry'
router: APIRouter = APIRouter(prefix="/pantry", tags=["pantry"])

def get_pantry_service(supabase: Client = Depends(get_supabase_client)) -> PantryService:
    """
    Dependency injector for PantryService.
    Returns a PantryService instance using the given Supabase client.
    """
    return PantryService(supabase)

async def add_single_pantry_item(
    *,
    pantry_item: PantryItemUpsert,
    household_id: UUID = Depends(get_current_household_id),  # The household for which to add the item, resolved from auth
    user_id: UUID = Depends(get_current_user_id),            # The acting user, resolved from auth
    pantry_service: PantryService = Depends(get_pantry_service),  # PantryService instance for business logic
) -> PantryItemUpsertResponse:
    """
    Add a single item to the user's household pantry.
    - Validates and persists an individual PantryItemUpsert.
    - Returns result model or raises HTTP 500 if insert fails.
    """
    result = await pantry_service.add_pantry_item_single(pantry_item, household_id, user_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add pantry item")
    return result

async def add_multiple_pantry_items(
    *,
    pantry_items: PantryItemsBulkCreateRequest,                   # Request model with list of items to add
    household_id: UUID = Depends(get_current_household_id),       # Household context from auth
    user_id: UUID = Depends(get_current_user_id),                 # User context from auth
    pantry_service: PantryService = Depends(get_pantry_service),  # Injected pantry service
) -> PantryItemsBulkCreateResponse:
    """
    Add multiple pantry items in a single request for the user's household.
    - Ensures items list is not empty.
    - Uses pantry_service to perform a batch add.
    - Raises HTTP 400 if no items, HTTP 500 if failed to add.
    """
    if not pantry_items.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pantry items provided")
    result = await pantry_service.add_pantry_item_bulk(pantry_items.items, household_id, user_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Bulk pantry add failed")
    return result

async def get_all_pantry_items(
    *,
    household_id: UUID = Depends(get_current_household_id),       # Get household context from auth
    pantry_service: PantryService = Depends(get_pantry_service),  # PantryService dependency
) -> List[PantryItem]:
    """
    Fetch all pantry items belonging to the current user's household.
    - Returns an empty list if query fails or no items found.
    """
    items = await pantry_service.get_household_pantry_items(household_id)
    if items is None:
        return []
    return items

async def get_my_pantry_items(
    *,
    user_id: UUID = Depends(get_current_user_id),                 # User who made the request
    household_id: UUID = Depends(get_current_household_id),       # User's household
    pantry_service: PantryService = Depends(get_pantry_service),  # PantryService dependency
) -> List[PantryItem]:
    """
    Fetch pantry items for the current user in their household.
    - Delegates to pantry_service method to scope by user.
    - Returns an empty list if none are found or operation fails.
    """
    items = await pantry_service.get_my_pantry_items(household_id, user_id)
    if items is None:
        return []
    return items

async def update_pantry_item(
    *,
    pantry_item: PantryItemUpsert,                                # Item data to update (must include primary key/id)
    household_id: UUID = Depends(get_current_household_id),       # Household constraint
    user_id: UUID = Depends(get_current_user_id),                 # User performing the update
    pantry_service: PantryService = Depends(get_pantry_service),  # PantryService business logic
) -> PantryItemUpsertResponse:
    """
    Update an existing pantry item.
    - Raises HTTP 404 if the item doesn't exist or cannot be updated (e.g., permissions, not found).
    - Otherwise returns updated PantryItemUpsertResponse.
    """
    result = await pantry_service.update_pantry_item(pantry_item, household_id, user_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pantry item not found or could not be updated")
    return result

async def delete_pantry_item(
    *,
    item_id: UUID,                                                # UUID of the item to delete (from request param/query)
    household_id: UUID = Depends(get_current_household_id),       # Household for scoping
    user_id: UUID = Depends(get_current_user_id),                 # User context
    pantry_service: PantryService = Depends(get_pantry_service),  # Pantry business logic
) -> PantryItemUpsertResponse:
    """
    Delete a pantry item identified by item_id in the user's household.
    - Returns deleted item details or raises HTTP 404 if not found.
    """
    result = await pantry_service.delete_pantry_item(item_id, household_id, user_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pantry item not found for deletion")
    return result

# --- FastAPI Route Registrations ---
# Register each function as a route in the /pantry group

router.post(
    "/add_item", response_model=PantryItemUpsertResponse
)(add_single_pantry_item)  # POST /pantry/add_item

router.post(
    "/bulk_add", response_model=PantryItemsBulkCreateResponse
)(add_multiple_pantry_items)  # POST /pantry/bulk_add

router.get(
    "/get_household_items", response_model=List[PantryItem]
)(get_all_pantry_items)  # GET /pantry/get_household_items

router.get(
    "/get_my_items", response_model=List[PantryItem]
)(get_my_pantry_items)  # GET /pantry/get_my_items

router.put(
    "/update_item", response_model=PantryItemUpsertResponse
)(update_pantry_item)  # PUT /pantry/update_item

router.delete(
    "/delete_item", response_model=PantryItemUpsertResponse
)(delete_pantry_item)  # DELETE /pantry/delete_item

# __all__ allows for explicit re-export of the router and API route callables,
# simplifying imports and discoverability when using `from ... import *`
__all__ = [
    "router",
    "add_single_pantry_item",
    "add_multiple_pantry_items",
    "get_all_pantry_items",
    "get_my_pantry_items",
    "update_pantry_item",
    "delete_pantry_item",
]
