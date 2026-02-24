from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import anyio
import pytest

from app.core.exceptions import AppError
from app.services import pantry_service as pantry_module
from app.services.pantry_service import PantryService


class _FakeTable:
    def __init__(self, name: str) -> None:
        self.name = name
        self._op = ""
        self._payload = None

    # Query builders (no-op for tests, we don't inspect filters)
    def select(self, *_: str, **__: object) -> "_FakeTable":
        return self

    def eq(self, *_: str, **__: object) -> "_FakeTable":
        return self

    def limit(self, *_: int, **__: object) -> "_FakeTable":
        return self

    def update(self, payload: object) -> "_FakeTable":
        self._op = "update"
        self._payload = payload
        return self

    def delete(self) -> "_FakeTable":
        self._op = "delete"
        return self

    def upsert(self, payload: object) -> "_FakeTable":
        self._op = "upsert"
        self._payload = payload
        return self

    def execute(self) -> SimpleNamespace:
        if self.name == "household_members":
            # Simulate that membership exists
            return SimpleNamespace(data=[{"id": "member-1"}])
        if self.name == "pantry_items" and self._op in {"upsert", "update"}:
            # Basic happy-path response for single-row operations
            row = (
                self._payload.copy()
                if isinstance(self._payload, dict)
                else (self._payload[0] if isinstance(self._payload, list) else {})
            )
            row.setdefault("id", str(uuid4()))
            row.setdefault("quantity", 1)
            return SimpleNamespace(data=[row])
        if self.name == "pantry_items" and self._op == "delete":
            return SimpleNamespace(data=[{"id": "deleted-id", "quantity": 1}])
        if self.name == "pantry_embeddings" and self._op == "upsert":
            # Embedding writes are not inspected in these tests
            return SimpleNamespace(data=[{}])
        # Default: no data
        return SimpleNamespace(data=[])


class _FakeSupabase:
    def table(self, name: str) -> _FakeTable:
        return _FakeTable(name)


class _FakeEmbeddingsClient:
    def embed_documents(self, contents: list[str]) -> list[list[float]]:
        # Return one small vector per document
        return [[0.1, 0.2, 0.3] for _ in contents]


@pytest.fixture(autouse=True)
def _patch_thread_run_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run anyio.to_thread.run_sync lambdas synchronously in tests."""

    def _run_sync(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(anyio.to_thread, "run_sync", _run_sync)


@pytest.fixture
def fake_service(monkeypatch: pytest.MonkeyPatch) -> PantryService:
    """PantryService wired with fake Supabase and embedding client."""
    monkeypatch.setattr(pantry_module, "embeddings_client", lambda: _FakeEmbeddingsClient())
    return PantryService(supabase=_FakeSupabase())


@pytest.mark.anyio
async def test_add_pantry_item_single_success(fake_service: PantryService) -> None:
    from app.models.pantry import PantryItemUpsert

    pantry_item = PantryItemUpsert(
        id=None,
        name="Milk",
        category="Dairy",
        quantity=1,
        unit="litre",
        expiry_date=None,
        expiry_visible=True,
    )
    household_id = uuid4()
    user_id = uuid4()

    result = await fake_service.add_pantry_item_single(
        pantry_item=pantry_item,
        household_id=household_id,
        user_id=user_id,
    )

    assert result.id is not None
    assert result.is_new is True
    assert result.new_quantity == 1.0
    assert result.embedding_generated is True


@pytest.mark.anyio
async def test_add_pantry_item_single_missing_membership_raises_app_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.models.pantry import PantryItemUpsert

    async def _ensure_user_in_household_raises(*_: object, **__: object) -> None:  # type: ignore[return-type]
        raise AppError("User is not a member of the specified household", status_code=403)

    monkeypatch.setattr(
        pantry_module,
        "_ensure_user_in_household",
        _ensure_user_in_household_raises,
    )

    service = PantryService(supabase=_FakeSupabase())
    pantry_item = PantryItemUpsert(
        id=None,
        name="Bread",
        category="Bakery",
        quantity=1,
        unit="loaf",
        expiry_date=None,
        expiry_visible=True,
    )

    with pytest.raises(AppError) as exc_info:
        await service.add_pantry_item_single(
            pantry_item=pantry_item,
            household_id=uuid4(),
            user_id=uuid4(),
        )

    assert "User is not a member of the specified household" in str(exc_info.value)


@pytest.mark.anyio
async def test_get_household_pantry_items_db_error_raises_app_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _run_sync_raises(fn, *args, **kwargs):  # type: ignore[return-type]
        raise RuntimeError("db down")

    monkeypatch.setattr(anyio.to_thread, "run_sync", _run_sync_raises)

    service = PantryService(supabase=_FakeSupabase())

    with pytest.raises(AppError) as exc_info:
        await service.get_household_pantry_items(household_id=uuid4())

    assert "Failed to fetch household pantry items" in str(exc_info.value)


@pytest.mark.anyio
async def test_delete_pantry_item_not_found_raises_app_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _EmptyDeleteTable(_FakeTable):
        def execute(self) -> SimpleNamespace:
            return SimpleNamespace(data=[])

    class _DeleteNotFoundSupabase(_FakeSupabase):
        def table(self, name: str) -> _FakeTable:
            if name == "pantry_items":
                return _EmptyDeleteTable(name)
            return super().table(name)

    service = PantryService(supabase=_DeleteNotFoundSupabase())

    with pytest.raises(AppError) as exc_info:
        await service.delete_pantry_item(item_id=uuid4(), household_id=uuid4(), user_id=uuid4())

    assert "Pantry item not found or not owned by user" in str(exc_info.value)

