from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends
from supabase import Client

from app.deps.supabase import get_supabase_client, get_supabase_service_role_client
from app.models.household import (
    HouseholdConvertToJoinableRequest,
    HouseholdJoinRequest,
    HouseholdJoinResponse,
    HouseholdLeaveResponse,
    HouseholdResponse,
)
from app.services.auth import get_current_user_id
from app.services.house_hold_service import HouseholdService
from app.models.household import HouseholdCreateRequest

# Initialize FastAPI APIRouter for household endpoints, with prefix '/households'
# All endpoints in this router will be tagged as 'households' in FastAPI documentation
router: APIRouter = APIRouter(prefix="/households", tags=["households"])

def get_household_service(supabase: Client = Depends(get_supabase_client)) -> HouseholdService:
    """
    Dependency provider for HouseholdService.
    Returns a HouseholdService instance using the provided Supabase client.
    """
    return HouseholdService(supabase)


async def create_household(
    *,
    body: HouseholdCreateRequest,
    user_id: UUID = Depends(get_current_user_id),
    household_service: HouseholdService = Depends(get_household_service),
    supabase_admin: Client = Depends(get_supabase_service_role_client),
) -> HouseholdResponse:
    """
    Create a new household, making the current user the owner and member.

    Args:
        body: The data for household creation (name, etc.)
        user_id: The ID of the currently authenticated user (from auth dependency)
        household_service: Instance of HouseholdService, injected via dependency
        supabase_admin: Service-role Supabase client (for privileged DB ops)

    Returns:
        HouseholdResponse: Metadata about the newly created household
    """
    return await household_service.create_household(body, user_id, supabase_admin)


# Redundant declaration: get_household_service already defined above.
def get_household_service(supabase: Client = Depends(get_supabase_client)) -> HouseholdService:
    """
    Dependency provider for HouseholdService.
    Returns a HouseholdService instance using the provided Supabase client.
    """
    return HouseholdService(supabase)


async def join_household(
    *,
    body: HouseholdJoinRequest,
    user_id: UUID = Depends(get_current_user_id),
    household_service: HouseholdService = Depends(get_household_service),
    supabase_admin: Client = Depends(get_supabase_service_role_client),
) -> HouseholdJoinResponse:
    """
    Join a household using an invite code.

    - The user's membership is switched to the target household.
    - The user's pantry items are moved to the new household.
    - Leaves the user's current household if present.

    Args:
        body: HouseholdJoinRequest containing the invite code.
        user_id: UUID of the currently authenticated user.
        household_service: HouseholdService instance injected.
        supabase_admin: Service-role Supabase client.

    Returns:
        HouseholdJoinResponse: Details about the join operation.
    """
    return await household_service.join_household_by_invite(
        body.invite_code,
        user_id,
        supabase_admin,
    )


async def leave_household(
    *,
    user_id: UUID = Depends(get_current_user_id),
    household_service: HouseholdService = Depends(get_household_service),
    supabase_admin: Client = Depends(get_supabase_service_role_client),
) -> HouseholdLeaveResponse:
    """
    Leave the user's current household and switch them to a new personal household.

    - Creates a new personal household if needed.
    - All of the user's pantry items are moved into the new personal household.
    - The user is removed as a member from the old household and added to the new.

    Args:
        user_id: UUID of current authenticated user.
        household_service: HouseholdService dependency.
        supabase_admin: Admin client for database ops.

    Returns:
        HouseholdLeaveResponse: Info about items moved, new household, etc.
    """
    return await household_service.leave_household(user_id, supabase_admin)


async def convert_to_joinable(
    *,
    body: HouseholdConvertToJoinableRequest | None = Body(None),
    user_id: UUID = Depends(get_current_user_id),
    household_service: HouseholdService = Depends(get_household_service),
    supabase_admin: Client = Depends(get_supabase_service_role_client),
) -> HouseholdResponse:
    """
    Convert the user's personal household into a joinable (shared) household.

    - Only the owner of a personal household can do this.
    - Turns off the 'is_personal' flag and optionally changes the name.
    - Returns the now-joinable household (with invite code, etc).

    Args:
        body: HouseholdConvertToJoinableRequest with optional new name.
        user_id: UUID of the acting user (must be owner).
        household_service: HouseholdService instance.
        supabase_admin: Admin client.

    Returns:
        HouseholdResponse: Details about the updated/joinable household.
    """
    name = body.name if body else None
    return await household_service.convert_personal_to_joinable(
        user_id,
        supabase_admin,
        name=name,
    )


# Register endpoints with the router, wiring POST requests to handler functions.
# Each has an explicit response model for FastAPI OpenAPI docs.

router.post("/join", response_model=HouseholdJoinResponse)(join_household)
router.post("/leave", response_model=HouseholdLeaveResponse)(leave_household)
router.post("/create", response_model=HouseholdResponse)(create_household)
router.post("/convert-to-joinable", response_model=HouseholdResponse)(convert_to_joinable)

# This controls what names get exported from this module (e.g., for import *)
__all__ = [
    "router",
    "join_household",
    "leave_household",
    "convert_to_joinable",
]
