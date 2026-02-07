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

router: APIRouter = APIRouter(prefix="/households", tags=["households"])

async def create_household(
    *,
    body: HouseholdCreateRequest,
    user_id: UUID = Depends(get_current_user_id),
    household_service: HouseholdService = Depends(get_household_service),
    supabase_admin: Client = Depends(get_supabase_service_role_client),
) -> HouseholdResponse:
    """
    Create a new household.
    """
    return await household_service.create_household(body, user_id, supabase_admin)


def get_household_service(supabase: Client = Depends(get_supabase_client)) -> HouseholdService:
    return HouseholdService(supabase)


async def join_household(
    *,
    body: HouseholdJoinRequest,
    user_id: UUID = Depends(get_current_user_id),
    household_service: HouseholdService = Depends(get_household_service),
    supabase_admin: Client = Depends(get_supabase_service_role_client),
) -> HouseholdJoinResponse:
    """
    Join a household by invite code. Moves your pantry items into the new household
    and switches your membership from your current household.
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
    Leave the current household and switch to a new personal household.
    Your pantry items are moved to the new personal household.
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
    Convert your personal household to a joinable (shared) household.
    Others can join using the invite code; they will leave their previous
    household and their pantry items will move with them.
    """
    name = body.name if body else None
    return await household_service.convert_personal_to_joinable(
        user_id,
        supabase_admin,
        name=name,
    )


router.post("/join", response_model=HouseholdJoinResponse)(join_household)
router.post("/leave", response_model=HouseholdLeaveResponse)(leave_household)
router.post("/create", response_model=HouseholdResponse)(create_household)
router.post("/convert-to-joinable", response_model=HouseholdResponse)(convert_to_joinable)

__all__ = [
    "router",
    "join_household",
    "leave_household",
    "convert_to_joinable",
]
