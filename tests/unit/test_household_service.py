from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import anyio
import pytest

from app.core.exceptions import AppError
from app.models.household import HouseholdCreate
from app.services.household_service import HouseholdService


class _FakeTable:
    def __init__(self, name: str, data: list[dict] | None = None) -> None:
        self.name = name
        self._data = data or []
        self._op = ""
        self._payload = None

    def select(self, *_: str, **__: object) -> "_FakeTable":
        return self

    def eq(self, *_: str, **__: object) -> "_FakeTable":
        return self

    def limit(self, *_: int, **__: object) -> "_FakeTable":
        return self

    def insert(self, payload: object) -> "_FakeTable":
        self._op = "insert"
        self._payload = payload
        return self

    def execute(self) -> SimpleNamespace:
        if self.name == "household_members":
            return SimpleNamespace(data=self._data)
        if self.name == "households" and self._op == "insert":
            row = (
                self._payload.copy()
                if isinstance(self._payload, dict)
                else (self._payload[0] if isinstance(self._payload, list) else {})
            )
            row.setdefault("id", str(uuid4()))
            row.setdefault("created_at", "2024-01-01T00:00:00Z")
            row.setdefault("is_personal", False)
            return SimpleNamespace(data=[row])
        return SimpleNamespace(data=[])


class _FakeSupabase:
    def __init__(self, membership_rows: list[dict] | None = None) -> None:
        self._membership_rows = membership_rows or []

    def table(self, name: str) -> _FakeTable:
        if name == "household_members":
            return _FakeTable(name, data=self._membership_rows)
        return _FakeTable(name)


@pytest.fixture(autouse=True)
def _patch_thread_run_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    def _run_sync(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(anyio.to_thread, "run_sync", _run_sync)


@pytest.mark.anyio
async def test_create_household_rejects_when_user_already_member() -> None:
    service = HouseholdService(supabase=_FakeSupabase(membership_rows=[{"id": "member-1"}]))
    household = HouseholdCreate(name="Test Household", is_personal=False)

    with pytest.raises(AppError) as exc_info:
        await service.create_household(
            household=household,
            user_id=uuid4(),
            supabase_admin=None,
        )

    assert "User is already a member of a household" in str(exc_info.value)


@pytest.mark.anyio
async def test_create_household_success_creates_row() -> None:
    service = HouseholdService(supabase=_FakeSupabase(membership_rows=[]))
    household = HouseholdCreate(name="Group Household", is_personal=False)
    user_id = uuid4()

    result = await service.create_household(
        household=household,
        user_id=user_id,
        supabase_admin=None,
    )

    assert result.id is not None
    assert result.name == "Group Household"
