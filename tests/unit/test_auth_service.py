from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import anyio
import pytest

from app.core.exceptions import AppError
from app.services import auth as auth_module
from app.services.auth import get_current_household_id, get_current_user_id


class _FakeUser:
    def __init__(self, user_id: object | None) -> None:
        self.id = user_id


@pytest.mark.anyio
async def test_get_current_user_id_happy_path() -> None:
    user_id = uuid4()
    user = _FakeUser(user_id)

    result = await get_current_user_id(user=user)

    assert result == user_id


@pytest.mark.anyio
async def test_get_current_user_id_missing_id_raises_app_error() -> None:
    user = _FakeUser(None)

    with pytest.raises(AppError) as exc_info:
        await get_current_user_id(user=user)

    assert "missing user ID" in str(exc_info.value)


@pytest.mark.anyio
async def test_get_current_user_id_invalid_uuid_raises_app_error() -> None:
    user = _FakeUser("not-a-uuid")

    with pytest.raises(AppError) as exc_info:
        await get_current_user_id(user=user)

    assert "invalid user ID" in str(exc_info.value)


@pytest.mark.anyio
async def test_get_current_household_id_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    household_id = uuid4()

    class _FakeTable:
        def select(self, *_: str, **__: object) -> "_FakeTable":
            return self

        def eq(self, *_: str, **__: object) -> "_FakeTable":
            return self

        def limit(self, *_: int, **__: object) -> "_FakeTable":
            return self

        def execute(self):
            return SimpleNamespace(data=[{"household_id": str(household_id)}])

    class _FakeSupabase:
        def table(self, name: str) -> _FakeTable:  # noqa: ARG002
            return _FakeTable()

    def _run_sync(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(anyio.to_thread, "run_sync", _run_sync)

    result = await get_current_household_id(user_id=user_id, supabase=_FakeSupabase())

    assert result == household_id


@pytest.mark.anyio
async def test_get_current_household_id_no_membership_raises_app_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()

    class _EmptyTable:
        def select(self, *_: str, **__: object) -> "_EmptyTable":
            return self

        def eq(self, *_: str, **__: object) -> "_EmptyTable":
            return self

        def limit(self, *_: int, **__: object) -> "_EmptyTable":
            return self

        def execute(self):
            return SimpleNamespace(data=[])

    class _FakeSupabase:
        def table(self, name: str) -> _EmptyTable:  # noqa: ARG002
            return _EmptyTable()

    def _run_sync(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(anyio.to_thread, "run_sync", _run_sync)

    with pytest.raises(AppError) as exc_info:
        await get_current_household_id(user_id=user_id, supabase=_FakeSupabase())

    assert "not a member of any household" in str(exc_info.value)

