from __future__ import annotations

import secrets
import string
from datetime import datetime
from typing import List, Dict, Optional
from uuid import UUID

import anyio
from fastapi import HTTPException, status
from supabase import Client

from models.household import (
    Household,
    HouseholdCreate,
    HouseholdUpdate,
    HouseholdResponse,
    HouseholdListResponse,
    HouseholdMember,
    HouseholdMemberCreate,
    HouseholdMemberUpdate,
    HouseholdMemberResponse,
    HouseholdMemberListResponse,
    HouseholdJoinResponse,
    HouseholdLeaveResponse,
)
from utils.date_time_styling import format_iso_datetime, format_iso_date, format_display_date


def _iso_now() -> str:
    """
    Helper function to return the current time formatted as an ISO datetime string.
    """
    return format_iso_datetime(value=datetime.now())


class HouseholdService:
    def __init__(self, supabase: Client) -> None:
        # Store the Supabase database client for later use in data operations.
        self.supabase = supabase

    async def create_household(self, household: HouseholdCreate, user_id: UUID) -> HouseholdResponse:
        """
        Create a new household.

        Steps:
          1. Make sure this user is not already in a household.
          2. Create a new household using input data.
          3. Add the user as the owner and member of this new household.

        Args:
            household: HouseholdCreate - data for the new household.
            user_id: UUID - the user creating the household.

        Returns:
            HouseholdResponse - basic info about the new household.

        Raises:
            HTTPException: 400 if user is already a member,
                           500 if the household creation fails.
        """

        # Step 1: Check membership - user should not already be part of any household.
        membership_response = await anyio.to_thread.run_sync(
            lambda: (
                self.supabase.table("household_members")
                    .select("id")
                    .eq("user_id", str(user_id))
                    .limit(1)
                    .execute()
            )
        )
        if getattr(membership_response, "data", None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of a household",
            )

        # Step 2: Create the household.
        household_response = await anyio.to_thread.run_sync(
            lambda: (
                self.supabase.table("households")
                .insert(household.model_dump())
                .select("*")
                .execute()
            )
        )
        # Error if creation fails.
        if not getattr(household_response, "data", None):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create household",
            )

        # Step 3: Add the user to the household as an owner & member.
        await anyio.to_thread.run_sync(
            lambda: (
                self.supabase.table("household_members")
                .insert({
                    "user_id": str(user_id),
                    "household_id": str(household_response.data[0]["id"]),
                    "joined_at": format_iso_datetime(value=datetime.now()),
                })
                .select("*")
                .execute()
            )
        )

        # Return the response model with new household details.
        return HouseholdResponse(
            id=UUID(household_response.data[0]["id"]),
            name=household_response.data[0]["name"],
            created_at=household_response.data[0]["created_at"],
            invite_code=household_response.data[0]["invite_code"],
            is_personal=household_response.data[0]["is_personal"],
        )

    async def join_household_by_invite(
        self,
        invite_code: str,
        user_id: UUID,
        supabase_admin: Client,
    ) -> HouseholdJoinResponse:
        """
        Join a household by invite code. This will:
          1. Validate the invite code and household.
          2. Ensure the user is currently in a household.
          3. Reject if already in target household.
          4. Migrate the user's pantry items to the new household.
          5. Remove user from their old household and add them to the new one.

        Args:
            invite_code (str): The invite code for the household.
            user_id (UUID): The user joining.
            supabase_admin (Client): Admin-level Supabase client.

        Returns:
            HouseholdJoinResponse: Includes the new household info and number of items moved.

        Raises:
            HTTPException: Various reasons (see inline error checks).
        """
        # Step 1: Sanitize and validate invite code.
        code = invite_code.upper().strip()
        if not code or len(code) != 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid invite code",
            )

        # Step 2: Fetch target household by invite code.
        target = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("households")
                .select("id, name, invite_code, is_personal, created_at")
                .eq("invite_code", code)
                .limit(1)
                .execute()
            )
        )
        if not getattr(target, "data", None) or len(target.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Household not found for this invite code",
            )
        target_row = target.data[0]
        # Can't join a personal household via invite code.
        if target_row.get("is_personal"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot join a personal household via invite code",
            )
        new_household_id = UUID(target_row["id"])

        # Step 3: Get current household membership.
        membership = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("household_members")
                .select("household_id")
                .eq("user_id", str(user_id))
                .limit(1)
                .execute()
            )
        )
        if not getattr(membership, "data", None) or len(membership.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not in any household",
            )
        old_household_id = UUID(membership.data[0]["household_id"])
        # Don't rejoin the same household.
        if old_household_id == new_household_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already in this household",
            )

        # Step 4: Move all of user's pantry items to new household.
        updated = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("pantry_items")
                .update({
                    "household_id": str(new_household_id),
                    "updated_at": _iso_now(),
                })
                .eq("household_id", str(old_household_id))
                .eq("owner_id", str(user_id))
                .execute()
            )
        )
        items_moved = len(getattr(updated, "data", None) or [])

        # Step 5: Remove user from old household and add to the new one.
        await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("household_members")
                .delete()
                .eq("user_id", str(user_id))
                .execute()
            )
        )
        await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("household_members")
                .insert({
                    "user_id": str(user_id),
                    "household_id": str(new_household_id),
                    "joined_at": _iso_now(),
                })
                .execute()
            )
        )

        # Pack household info + moved count as a response.
        return HouseholdJoinResponse(
            household=HouseholdResponse(
                id=new_household_id,
                name=target_row["name"],
                created_at=target_row["created_at"],
                invite_code=target_row["invite_code"],
                is_personal=target_row["is_personal"],
            ),
            items_moved=items_moved,
        )

    async def leave_household(
        self,
        user_id: UUID,
        supabase_admin: Client,
    ) -> HouseholdLeaveResponse:
        """
        Leave the user's current household and move them back into a fresh personal household.
        Moves all their pantry items as well.

        Steps:
          1. Confirm user is in a group (not already personal).
          2. Create a new personal household (with unique invite code).
          3. Move all user's pantry items to new personal household.
          4. Remove user from their group and add as only member & owner of the new one.
        
        Args:
            user_id (UUID): The user leaving their group.
            supabase_admin (Client): Admin Supabase client.

        Returns:
            HouseholdLeaveResponse: Details of the switch and number of items moved.

        Raises:
            HTTPException: 400/500 for various reasons.
        """

        # 1. Get current household id of the user.
        membership = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("household_members")
                .select("household_id")
                .eq("user_id", str(user_id))
                .limit(1)
                .execute()
            )
        )
        if not getattr(membership, "data", None) or len(membership.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not in any household",
            )
        current_household_id = UUID(membership.data[0]["household_id"])

        # 2. Make sure not already in a personal household.
        current = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("households")
                .select("id, name, is_personal")
                .eq("id", str(current_household_id))
                .limit(1)
                .execute()
            )
        )
        if getattr(current, "data", None) and len(current.data) > 0 and current.data[0].get("is_personal"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already in personal household",
            )

        # Helper to generate a random 6-digit invite code
        def make_invite_code() -> str:
            return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

        # 3. Create the new personal household, retrying if invite code collides (up to 5 times).
        personal_name = "My Household"
        for _ in range(5):
            invite_code = make_invite_code()
            try:
                insert_resp = await anyio.to_thread.run_sync(
                    lambda ic=invite_code: (
                        supabase_admin.table("households")
                        .insert({
                            "name": personal_name,
                            "invite_code": ic,
                            "is_personal": True,
                            "owner_id": str(user_id),
                        })
                        .select("id, name, invite_code, created_at")
                        .execute()
                    )
                )
            except Exception:
                continue
            if getattr(insert_resp, "data", None) and len(insert_resp.data) > 0:
                break
        else:
            # Could not find a unique invite code after 5 tries.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create personal household",
            )

        personal_row = insert_resp.data[0]
        personal_household_id = UUID(personal_row["id"])

        # 4. Move all pantry items to the new personal household.
        updated = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("pantry_items")
                .update({
                    "household_id": str(personal_household_id),
                    "updated_at": _iso_now(),
                })
                .eq("household_id", str(current_household_id))
                .eq("owner_id", str(user_id))
                .execute()
            )
        )
        items_moved = len(getattr(updated, "data", None) or [])

        # 5. Remove the user from the old household.
        await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("household_members")
                .delete()
                .eq("user_id", str(user_id))
                .execute()
            )
        )
        # 6. Add the user as a member of the new personal household.
        await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("household_members")
                .insert({
                    "user_id": str(user_id),
                    "household_id": str(personal_household_id),
                    "joined_at": _iso_now(),
                })
                .execute()
            )
        )

        # Return details about the switch.
        return HouseholdLeaveResponse(
            message="Left household and switched to personal household",
            items_deleted=items_moved,
            new_household_id=personal_household_id,
            new_household_name=personal_row["name"],
        )

    async def convert_personal_to_joinable(
        self,
        user_id: UUID,
        supabase_admin: Client,
        name: Optional[str] = None,
    ) -> HouseholdResponse:
        """
        Convert a personal household to a shared/joinable one.

        Steps:
          1. Look up the user's current household.
          2. Confirm it is both personal and the user is the owner.
          3. Update the household to set is_personal=False, and optionally change its name.

        Args:
            user_id (UUID): The user requesting conversion (must be owner)
            supabase_admin (Client): Admin Supabase client
            name (Optional[str]): Optional new name for the household

        Returns:
            HouseholdResponse: Info about the now-joinable household

        Raises:
            HTTPException: If user/ownership/household state invalid, or DB update fails.
        """

        # 1. Look up user's household membership.
        membership = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("household_members")
                .select("household_id")
                .eq("user_id", str(user_id))
                .limit(1)
                .execute()
            )
        )
        if not getattr(membership, "data", None) or len(membership.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not in any household",
            )
        household_id = UUID(membership.data[0]["household_id"])

        # 2. Fetch the household and check it's personal, and owned by this user.
        household = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("households")
                .select("id, name, invite_code, is_personal, created_at, owner_id")
                .eq("id", str(household_id))
                .limit(1)
                .execute()
            )
        )
        if not getattr(household, "data", None) or len(household.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Household not found",
            )
        row = household.data[0]
        if not row.get("is_personal"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Household is already joinable; only personal households can be converted",
            )
        if str(row.get("owner_id")) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the household owner can convert it to joinable",
            )

        # 3. Form the update payload: is_personal->False, maybe update name.
        update_payload: Dict[str, object] = {"is_personal": False}
        if name is not None and name.strip():
            update_payload["name"] = name.strip()

        # 4. Update the household in the DB.
        updated = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("households")
                .update(update_payload)
                .eq("id", str(household_id))
                .select("id, name, invite_code, is_personal, created_at")
                .execute()
            )
        )
        if not getattr(updated, "data", None) or len(updated.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update household",
            )
        out = updated.data[0]
        # Return the joinable household info as a response model.
        return HouseholdResponse(
            id=UUID(out["id"]),
            name=out["name"],
            created_at=out["created_at"],
            invite_code=out["invite_code"],
            is_personal=out["is_personal"],
        )

