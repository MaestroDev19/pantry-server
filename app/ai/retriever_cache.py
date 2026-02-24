from __future__ import annotations

import hashlib
import time
from typing import Dict, List, Optional, Tuple

from langchain_core.documents import Document

from app.core.logging import get_logger

logger = get_logger(__name__)


class RetrieverCache:
    """
    In-memory cache for vector store retrieval results.

    This is optimized for pantry RAG use-cases:
    - Keys include household id, query text, and top-k
    - Cache is invalidated explicitly by pantry write operations
    - A TTL is kept as a secondary safety net
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        # ttl_seconds is a safety net — primary invalidation is content-based via service hooks
        self._ttl = ttl_seconds
        # { cache_key: (documents, serialized, fetched_at, household_id) }
        self._store: Dict[str, Tuple[List[Document], str, float, str]] = {}
        # { household_id: last_known_updated_at } (reserved for future state-based invalidation)
        self._pantry_state: Dict[str, str] = {}

    def _make_key(self, household_id: str, query: str, k: int) -> str:
        raw = f"{household_id}:{query}:{k}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(
        self,
        household_id: str,
        query: str,
        k: int,
    ) -> Optional[Tuple[str, List[Document]]]:
        key = self._make_key(household_id, query, k)
        entry = self._store.get(key)
        if not entry:
            return None

        documents, serialized, fetched_at, _ = entry

        # TTL safety net
        if time.monotonic() - fetched_at > self._ttl:
            logger.debug("Retriever cache expired (TTL)", extra={"key": key[:12]})
            del self._store[key]
            return None

        return serialized, documents

    def set(
        self,
        household_id: str,
        query: str,
        k: int,
        documents: List[Document],
        serialized: str,
    ) -> None:
        key = self._make_key(household_id, query, k)
        self._store[key] = (documents, serialized, time.monotonic(), household_id)
        logger.debug(
            "Retriever cache set",
            extra={"key": key[:12], "household_id": household_id, "docs": len(documents)},
        )

    def invalidate_household(self, household_id: str) -> None:
        """Remove all cached entries for a household."""
        keys_to_delete = [
            key
            for key, (_, _, _, hh_id) in self._store.items()
            if hh_id == household_id
        ]
        for key in keys_to_delete:
            del self._store[key]
        self._pantry_state.pop(household_id, None)
        if keys_to_delete:
            logger.info(
                "Retriever cache invalidated for household",
                extra={"household_id": household_id, "keys_removed": len(keys_to_delete)},
            )

    def update_pantry_state(self, household_id: str, latest_updated_at: str) -> bool:
        """
        Returns True if the pantry state has changed (cache should be invalidated).
        Updates the stored state.
        """
        previous = self._pantry_state.get(household_id)
        if previous != latest_updated_at:
            self._pantry_state[household_id] = latest_updated_at
            return True
        return False


_cache = RetrieverCache(ttl_seconds=300)


def get_retriever_cache() -> RetrieverCache:
    return _cache

