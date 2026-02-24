from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class TTLCache:
    """
    In-memory TTL cache for caching function results.
    
    Stores key-value pairs with expiration times. Automatically evicts
    expired entries on access.
    """

    def __init__(self, default_ttl_seconds: int = 300) -> None:
        """
        Initialize cache with default TTL.
        
        Args:
            default_ttl_seconds: Default time-to-live in seconds (default: 5 minutes)
        """
        self._cache: dict[str, tuple[Any, float]] = {}
        self.default_ttl_seconds = default_ttl_seconds

    def get(self, key: str) -> Any | None:
        """
        Get value from cache if not expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        if key not in self._cache:
            return None
        
        value, expiry_time = self._cache[key]
        
        if time.time() > expiry_time:
            del self._cache[key]
            logger.debug("Cache entry expired", extra={"key": key})
            return None
        
        logger.debug("Cache hit", extra={"key": key})
        return value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """
        Store value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds (uses default if None)
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        expiry_time = time.time() + ttl
        self._cache[key] = (value, expiry_time)
        logger.debug("Cache entry set", extra={"key": key, "ttl_seconds": ttl})

    def delete(self, key: str) -> None:
        """Delete a cache entry."""
        if key in self._cache:
            del self._cache[key]
            logger.debug("Cache entry deleted", extra={"key": key})

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        logger.debug("Cache cleared")

    def _evict_expired(self) -> None:
        """Remove all expired entries."""
        current_time = time.time()
        expired_keys = [
            key for key, (_, expiry_time) in self._cache.items() if current_time > expiry_time
        ]
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug("Evicted expired entries", extra={"count": len(expired_keys)})

    def size(self) -> int:
        """Return number of entries in cache."""
        self._evict_expired()
        return len(self._cache)


_global_cache = TTLCache(default_ttl_seconds=300)


def get_cache() -> TTLCache:
    """Get the global cache instance."""
    return _global_cache


def cached(
    ttl_seconds: int = 300,
    key_func: Callable[..., str] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to cache function results with TTL.
    
    Args:
        ttl_seconds: Time-to-live in seconds for cached results
        key_func: Optional function to generate cache key from args/kwargs.
                  Defaults to str(args) + str(sorted(kwargs.items()))
    
    Example:
        @cached(ttl_seconds=60)
        async def get_user(user_id: UUID) -> User:
            ...
    """
    cache = get_cache()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl_seconds=ttl_seconds)
            return result

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl_seconds=ttl_seconds)
            return result

        if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        return sync_wrapper

    return decorator


__all__ = ["TTLCache", "get_cache", "cached"]
