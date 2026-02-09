"""Unit tests for app.core.exceptions."""
from __future__ import annotations

from fastapi import status

import pytest

from app.core.exceptions import AppError, app_error_handler


def test_app_error_default_status_code() -> None:
    exc = AppError("Something failed")
    assert exc.message == "Something failed"
    assert exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc.headers == {}


def test_app_error_custom_status_code() -> None:
    exc = AppError("Not found", status_code=status.HTTP_404_NOT_FOUND)
    assert exc.status_code == status.HTTP_404_NOT_FOUND


def test_app_error_with_headers() -> None:
    exc = AppError("Unauthorized", status_code=401, headers={"WWW-Authenticate": "Bearer"})
    assert exc.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.asyncio
async def test_app_error_handler_returns_json_response() -> None:
    from unittest.mock import MagicMock

    exc = AppError("Test error", status_code=status.HTTP_400_BAD_REQUEST)
    request = MagicMock()
    response = await app_error_handler(request, exc)
    assert response.status_code == 400
    assert response.body is not None
    import json

    body = json.loads(response.body.decode())
    assert body["error"] == "Test error"
    assert body["status_code"] == 400
