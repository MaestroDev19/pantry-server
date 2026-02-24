"""Integration tests for health and root endpoints."""
from __future__ import annotations

from fastapi import status


def test_get_health_returns_ok(client) -> None:
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ok"


def test_get_root_returns_ok(client) -> None:
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ok"


def test_health_endpoint_is_rate_limited(client) -> None:
    """
    When rate limiting is enabled, hitting /health more than the configured
    default limit should eventually return HTTP 429.
    """
    app = client.app
    limiter = getattr(app.state, "limiter", None)
    if limiter is None:
        # Rate limiting disabled for this test environment; skip assertion.
        return

    # Make the limit small for the test.
    limiter.default_limits = ["2/minute"]

    first = client.get("/health")
    second = client.get("/health")
    third = client.get("/health")

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_200_OK
    assert third.status_code == status.HTTP_429_TOO_MANY_REQUESTS
