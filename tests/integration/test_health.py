"""Integration tests for health and root endpoints."""
from __future__ import annotations


def test_get_health_returns_ok(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_get_root_returns_ok(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
