from __future__ import annotations

import secrets
import string
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

import anyio
from fastapi import status
from supabase import Client
from postgrest.exceptions import APIError

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.models.household import (
    HouseholdCreate,
    HouseholdResponse,
    HouseholdJoinResponse,
    HouseholdLeaveResponse,
)
from app.utils.date_time_styling import format_iso_datetime

logger = get_logger(__name__)

INVITE_CODE_LENGTH = 6
MAX_INVITE_CODE_RETRIES = 5
DEFAULT_PERSONAL_HOUSEHOLD_NAME = "My Household"
POSTGRES_UNIQUE_VIOLATION_CODE = "23505"


def _iso_now() -> str:
    return format_iso_datetime(value=datetime.now())


def _generate_invite_code() -> str:
    return "".join(
        secrets.choice(string.ascii_uppercase + string.digits)
        for _ in range(INVITE_CODE_LENGTH)
    )


def _response_has_data(response: Any) -> bool:
    data = getattr(response, "data", None)
    return bool(data) and len(data) > 0


def _first_row(response: Any) -> Dict[str, Any]:
    data = getattr(response, "data", None) or []
    return data[0] if data else {}


def _row_to_household_response(row: Dict[str, Any]) -> HouseholdResponse:
    return HouseholdResponse(
        id=UUID(row["id"]),
        name=row["name"],
        created_at=row["created_at"],
        invite_code=row["invite_code"],
        is_personal=row.get("is_personal", False),
    )


class HouseholdService:
    def __init__(self, supabase: Client) -> None:
        # Store the Supabase database client for later use in data operations.
        self.supabase = supabase

    async def create_household(
        self,
        household: HouseholdCreate,
        user_id: UUID,
        supabase_admin: Optional[Client] = None,
    ) -> HouseholdResponse:
        """
        Create a new household.

        Steps:
          1. Make sure this user is not already in a household.
          2. Create a new household using input data.
          3. Add the user as the owner and member of this new household.

        Uses supabase_admin (service role) when provided so that inserts bypass RLS;
        otherwise uses the anon client (requires RLS policies allowing insert).

        Args:
            household: HouseholdCreate - data for the new household.
            user_id: UUID - the user creating the household.
            supabase_admin: Optional service-role client for privileged inserts.

        Returns:
            HouseholdResponse - basic info about the new household.

        Raises:
            AppError: 400 if user is already a member,
                      500 if the household creation fails.
        """
        client = supabase_admin if supabase_admin is not None else self.supabase
        is_personal = bool(getattr(household, "is_personal", False))

        membership_response = await anyio.to_thread.run_sync(
            lambda: (
                client.table("household_members")
                    .select("id")
                    .eq("user_id", str(user_id))
                    .limit(1)
                    .execute()
            )
        )
        if _response_has_data(membership_response):
            logger.error("Create household rejected: user already in a household", extra={"user_id": str(user_id)})
            raise AppError("User is already a member of a household", status_code=status.HTTP_400_BAD_REQUEST)

        if is_personal:
            existing_personal = await anyio.to_thread.run_sync(
                lambda: (
                    client.table("households")
                    .select("id, name, invite_code, is_personal, created_at")
                    .eq("owner_id", str(user_id))
                    .eq("is_personal", True)
                    .limit(1)
                    .execute()
                )
            )
            if _response_has_data(existing_personal):
                row = _first_row(existing_personal)
                logger.info(
                    "Reusing existing personal household for user",
                    extra={"user_id": str(user_id), "household_id": row["id"]},
                )
                return _row_to_household_response(row)

        payload: Dict[str, object] = {
            "name": household.name,
            "invite_code": _generate_invite_code(),
        }
        if is_personal:
            payload["is_personal"] = True
            payload["owner_id"] = str(user_id)

        try:
            household_response = await anyio.to_thread.run_sync(
                lambda: (
                    client.table("households")
                    .insert(payload)
                    .execute()
                )
            )
        except APIError as exc:
            details = exc.args[0] if exc.args else {}
            code = details.get("code") if isinstance(details, dict) else None

            if code == POSTGRES_UNIQUE_VIOLATION_CODE and is_personal:
                existing = await anyio.to_thread.run_sync(
                    lambda: (
                        client.table("households")
                        .select("id, name, invite_code, is_personal, created_at")
                        .eq("owner_id", str(user_id))
                        .eq("is_personal", True)
                        .limit(1)
                        .execute()
                    )
                )
                if _response_has_data(existing):
                    row = _first_row(existing)
                    logger.info(
                        "Personal household unique constraint hit, reusing existing",
                        extra={"user_id": str(user_id), "household_id": row["id"]},
                    )
                    return _row_to_household_response(row)

            logger.error(
                "Failed to create household (APIError)",
                extra={"user_id": str(user_id), "error": details},
            )
            raise AppError("Failed to create household", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from exc

        if not _response_has_data(household_response):
            logger.error("Failed to create household (no data from insert)", extra={"user_id": str(user_id)})
            raise AppError("Failed to create household", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not is_personal:
            await anyio.to_thread.run_sync(
                lambda: (
                    client.table("household_members")
                    .insert({
                        "user_id": str(user_id),
                        "household_id": str(household_response.data[0]["id"]),
                        "joined_at": format_iso_datetime(value=datetime.now()),
                    })
                    .execute()
                )
            )

        out = _row_to_household_response(_first_row(household_response))
        logger.info("Household created", extra={"user_id": str(user_id), "household_id": str(out.id)})
        return out

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
            AppError: Various reasons (see inline error checks).
        """
        code = invite_code.upper().strip()
        if not code or len(code) != INVITE_CODE_LENGTH:
            logger.error("Invalid invite code", extra={"user_id": str(user_id)})
            raise AppError("Invalid invite code", status_code=status.HTTP_400_BAD_REQUEST)

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
        if not _response_has_data(target):
            logger.error("Household not found for invite code", extra={"user_id": str(user_id), "invite_code": code})
            raise AppError("Household not found for this invite code", status_code=status.HTTP_404_NOT_FOUND)
        target_row = _first_row(target)
        # Can't join a personal household via invite code.
        if target_row.get("is_personal"):
            logger.error("Cannot join personal household via invite", extra={"user_id": str(user_id)})
            raise AppError("Cannot join a personal household via invite code", status_code=status.HTTP_400_BAD_REQUEST)
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
        if not _response_has_data(membership):
            logger.error("Join household: user not in any household", extra={"user_id": str(user_id)})
            raise AppError("User is not in any household", status_code=status.HTTP_400_BAD_REQUEST)
        old_household_id = UUID(_first_row(membership)["household_id"])
        # Don't rejoin the same household.
        if old_household_id == new_household_id:
            logger.info("Join household: already in target household", extra={"user_id": str(user_id), "household_id": str(new_household_id)})
            raise AppError("Already in this household", status_code=status.HTTP_400_BAD_REQUEST)

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

        logger.info("User joined household", extra={"user_id": str(user_id), "new_household_id": str(new_household_id), "items_moved": items_moved})
        return HouseholdJoinResponse(
            household=_row_to_household_response(target_row),
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
            AppError: 400/500 for various reasons.
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
        if not _response_has_data(membership):
            logger.error("Leave household: user not in any household", extra={"user_id": str(user_id)})
            raise AppError("User is not in any household", status_code=status.HTTP_400_BAD_REQUEST)
        current_household_id = UUID(_first_row(membership)["household_id"])

        current = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("households")
                .select("id, name, is_personal")
                .eq("id", str(current_household_id))
                .limit(1)
                .execute()
            )
        )
        if _response_has_data(current) and _first_row(current).get("is_personal"):
            logger.error("Leave household: already in personal household", extra={"user_id": str(user_id)})
            raise AppError("Already in personal household", status_code=status.HTTP_400_BAD_REQUEST)

        insert_resp = None
        for _ in range(MAX_INVITE_CODE_RETRIES):
            invite_code = _generate_invite_code()
            try:
                insert_resp = await anyio.to_thread.run_sync(
                    lambda ic=invite_code: (
                        supabase_admin.table("households")
                        .insert({
                            "name": DEFAULT_PERSONAL_HOUSEHOLD_NAME,
                            "invite_code": ic,
                            "is_personal": True,
                            "owner_id": str(user_id),
                        })
                        .execute()
                    )
                )
            except Exception:
                continue
            if _response_has_data(insert_resp):
                break
        else:
            logger.error("Leave household: failed to create personal household (invite code collision)", extra={"user_id": str(user_id)})
            raise AppError("Failed to create personal household", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        personal_row = _first_row(insert_resp)
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

        logger.info("User left household", extra={"user_id": str(user_id), "new_household_id": str(personal_household_id), "items_moved": items_moved})
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
            AppError: If user/ownership/household state invalid, or DB update fails.
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
        if not _response_has_data(membership):
            logger.error("Convert to joinable: user not in any household", extra={"user_id": str(user_id)})
            raise AppError("User is not in any household", status_code=status.HTTP_400_BAD_REQUEST)
        household_id = UUID(_first_row(membership)["household_id"])

        household = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("households")
                .select("id, name, invite_code, is_personal, created_at, owner_id")
                .eq("id", str(household_id))
                .limit(1)
                .execute()
            )
        )
        if not _response_has_data(household):
            logger.error("Convert to joinable: household not found", extra={"user_id": str(user_id), "household_id": str(household_id)})
            raise AppError("Household not found", status_code=status.HTTP_404_NOT_FOUND)
        row = _first_row(household)
        if not row.get("is_personal"):
            logger.error("Convert to joinable: household already joinable", extra={"user_id": str(user_id), "household_id": str(household_id)})
            raise AppError("Household is already joinable; only personal households can be converted", status_code=status.HTTP_400_BAD_REQUEST)
        if str(row.get("owner_id")) != str(user_id):
            logger.error("Convert to joinable: not owner", extra={"user_id": str(user_id), "household_id": str(household_id)})
            raise AppError("Only the household owner can convert it to joinable", status_code=status.HTTP_403_FORBIDDEN)

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
                .execute()
            )
        )
        if not _response_has_data(updated):
            logger.error("Convert to joinable: update failed", extra={"user_id": str(user_id), "household_id": str(household_id)})
            raise AppError("Failed to update household", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        out_row = _first_row(updated)
        logger.info("Household converted to joinable", extra={"user_id": str(user_id), "household_id": str(household_id)})
        return _row_to_household_response(out_row)
