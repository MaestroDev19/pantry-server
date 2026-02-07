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
    return format_iso_datetime(value=datetime.now())


class HouseholdService:
    def __init__(self, supabase: Client) -> None:
        # Store the Supabase database client for later use in data operations.
        self.supabase = supabase

    async def create_household(self, household: HouseholdCreate, user_id: UUID) -> HouseholdResponse:
        """
        Create a new household.
        Args:
            household: HouseholdCreate
            user_id: UUID
        Returns:
            HouseholdResponse
        """
        # Verify user is not already a member of a household
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
        # Create the household
        household_response = await anyio.to_thread.run_sync(
            lambda: (
                self.supabase.table("households")
                .insert(household.model_dump())
                .select("*")
                .execute()
            )
        )
        # If the household was not created, raise an error
        if not getattr(household_response, "data", None):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create household",
            )
        # Add the user to the household as an owner
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
        Join a household by invite code. Migrates the user's pantry items from their
        current household to the target household, then switches membership.
        Uses supabase_admin (service role) to bypass RLS for migration and membership.
        """
        code = invite_code.upper().strip()
        if not code or len(code) != 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid invite code",
            )

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
        if target_row.get("is_personal"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot join a personal household via invite code",
            )
        new_household_id = UUID(target_row["id"])

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
        if old_household_id == new_household_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already in this household",
            )

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
        Leave current household and return to a new personal household.
        Migrates the user's pantry items to the new personal household, then switches membership.
        """
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

        def make_invite_code() -> str:
            return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create personal household",
            )

        personal_row = insert_resp.data[0]
        personal_household_id = UUID(personal_row["id"])

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
                    "household_id": str(personal_household_id),
                    "joined_at": _iso_now(),
                })
                .execute()
            )
        )

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
        Convert the current user's personal household to a joinable (shared) household.
        Others can then join via the existing invite code; they will auto-leave their
        previous household and their items will move with them (existing join flow).
        Only the owner of a personal household can perform this conversion.
        """
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

        update_payload: Dict[str, object] = {"is_personal": False}
        if name is not None and name.strip():
            update_payload["name"] = name.strip()

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
        return HouseholdResponse(
            id=UUID(out["id"]),
            name=out["name"],
            created_at=out["created_at"],
            invite_code=out["invite_code"],
            is_personal=out["is_personal"],
        )
