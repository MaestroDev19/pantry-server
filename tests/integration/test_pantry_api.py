"""Integration tests for pantry API routes.

Pantry routes require authentication (get_current_user_id, get_current_household_id).
These tests verify route registration and error responses without real Supabase.
"""


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
    # No credentials: FastAPI security returns 403 Forbidden
    assert response.status_code == 403


def test_pantry_get_household_items_requires_auth(client) -> None:
    """GET /pantry/get_household_items without auth returns 403."""
    response = client.get("/pantry/get_household_items")
    assert response.status_code == 403
