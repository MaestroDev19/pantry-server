"""Integration tests for households API routes.

Household routes require authentication. These tests verify route registration,
403 responses without auth, and basic happy-path and error wiring with faked services.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import status

from app.models.household import (
    HouseholdCreateRequest,
    HouseholdJoinRequest,
    HouseholdJoinResponse,
    HouseholdLeaveResponse,
    HouseholdResponse,
)
from app.routers.household import get_household_service
from app.services.auth import get_current_user_id
from app.core.exceptions import AppError


def test_households_join_requires_auth(client) -> None:
    """POST /households/join without auth returns 403."""
    response = client.post(
        "/households/join",
        json={"invite_code": "ABC123"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_households_leave_requires_auth(client) -> None:
    """POST /households/leave without auth returns 403."""
    response = client.post("/households/leave")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_households_create_authenticated_success(client) -> None:
    """POST /households/create with auth and fake service returns 200."""
    app = client.app
    user_id = uuid4()

    class _FakeHouseholdService:
        async def create_household(
            self,
            household: HouseholdCreateRequest,
            user_id_arg,
            supabase_admin=None,  # noqa: ARG002
        ) -> HouseholdResponse:
            assert user_id_arg == user_id
            return HouseholdResponse(
                id=uuid4(),
                name=household.name,
                invite_code="ABC123",
                is_personal=False,
                created_at="2024-01-01T00:00:00Z",
            )

    app.dependency_overrides[get_current_user_id] = lambda: user_id
    app.dependency_overrides[get_household_service] = lambda: _FakeHouseholdService()

    try:
        response = client.post(
            "/households/create",
            json={"name": "My Household", "is_personal": False},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "My Household"
        assert data["invite_code"] == "ABC123"
    finally:
        app.dependency_overrides.clear()


def test_households_join_invalid_invite_returns_400(client) -> None:
    """POST /households/join returns 400 when service raises AppError."""
    app = client.app
    user_id = uuid4()

    class _FakeHouseholdService:
        async def join_household_by_invite(self, *_, **__):
            raise AppError("Invalid invite", status_code=status.HTTP_400_BAD_REQUEST)

    app.dependency_overrides[get_current_user_id] = lambda: user_id
    app.dependency_overrides[get_household_service] = lambda: _FakeHouseholdService()

    try:
        response = client.post(
            "/households/join",
            json={"invite_code": "ABC123"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    finally:
        app.dependency_overrides.clear()
