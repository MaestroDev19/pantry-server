"""Shared pytest fixtures for unit and integration tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def test_settings() -> SimpleNamespace:
    """Minimal settings for test app (no real env/Supabase)."""
    return SimpleNamespace(
        app_env="test",
        app_name="pantry-server-test",
    )


@pytest.fixture
def app(test_settings: SimpleNamespace):
    """FastAPI app instance with test settings."""
    return create_app(settings=test_settings)


@pytest.fixture
def client(app):
    """HTTP client for integration tests (sync TestClient)."""
    return TestClient(app)
