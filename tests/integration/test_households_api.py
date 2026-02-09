"""Integration tests for households API routes.

Household routes require authentication. These tests verify route registration
and error responses without real Supabase.
"""


def test_households_join_requires_auth(client) -> None:
    """POST /households/join without auth returns 403."""
    response = client.post(
        "/households/join",
        json={"invite_code": "ABC123"},
    )
    assert response.status_code == 403


def test_households_leave_requires_auth(client) -> None:
    """POST /households/leave without auth returns 403."""
    response = client.post("/households/leave")
    assert response.status_code == 403
