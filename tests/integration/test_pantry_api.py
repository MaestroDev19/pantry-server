"""Integration tests for pantry API routes.

Pantry routes require authentication (get_current_user_id, get_current_household_id).
These tests verify route registration, error responses, and basic happy-path wiring
without hitting real Supabase.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import status

from app.models.pantry import PantryItemUpsertResponse, PantryItemsBulkCreateResponse
from app.routers.pantry import get_pantry_service
from app.services.auth import get_current_household_id, get_current_user_id


def test_pantry_add_item_requires_auth(client) -> None:
    """POST /pantry/add_item without auth returns 403 (no Bearer token)."""
    response = client.post(
        "/pantry/add_item",
        json={
            "name": "Milk",
            "category": "Dairy",
            "quantity": 1,
            "unit": "litre",
        },
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_pantry_get_household_items_requires_auth(client) -> None:
    """GET /pantry/get_household_items without auth returns 403."""
    response = client.get("/pantry/get_household_items")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_pantry_add_item_authenticated_success(client) -> None:
    """POST /pantry/add-item with auth and fake service returns 200 and payload."""
    app = client.app
    user_id = uuid4()
    household_id = uuid4()

    class _FakePantryService:
        async def add_pantry_item_single(self, *_, **__) -> PantryItemUpsertResponse:
            return PantryItemUpsertResponse(
                id=uuid4(),
                is_new=True,
                old_quantity=0.0,
                new_quantity=1.0,
                message="ok",
                embedding_generated=False,
            )

    app.dependency_overrides[get_current_user_id] = lambda: user_id
    app.dependency_overrides[get_current_household_id] = lambda: household_id
    app.dependency_overrides[get_pantry_service] = lambda: _FakePantryService()

    try:
        response = client.post(
            "/pantry/add-item",
            json={
                "id": None,
                "name": "Milk",
                "category": "Dairy",
                "quantity": 1,
                "unit": "litre",
                "expiry_date": None,
                "expiry_visible": True,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_new"] is True
        assert data["new_quantity"] == 1.0
    finally:
        app.dependency_overrides.clear()


def test_pantry_update_item_not_found_returns_404(client) -> None:
    """PUT /pantry/update-item returns 404 when service reports missing item."""
    app = client.app
    user_id = uuid4()
    household_id = uuid4()

    class _FakePantryService:
        async def update_pantry_item(self, *_, **__):
            return None

    app.dependency_overrides[get_current_user_id] = lambda: user_id
    app.dependency_overrides[get_current_household_id] = lambda: household_id
    app.dependency_overrides[get_pantry_service] = lambda: _FakePantryService()

    try:
        response = client.put(
            "/pantry/update-item",
            json={
                "id": str(uuid4()),
                "name": "Milk",
                "category": "Dairy",
                "quantity": 2,
                "unit": "litre",
                "expiry_date": None,
                "expiry_visible": True,
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
    finally:
        app.dependency_overrides.clear()
