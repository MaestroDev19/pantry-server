from __future__ import annotations

from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

limiter = Limiter(key_func=get_remote_address)


def get_rate_limit_decorator(calls_per_minute: int | None = None):
    """
    Return a SlowAPI limit decorator honoring RATE_LIMIT_ENABLED.
    When rate limiting is disabled, this returns a no-op decorator.
    """

    if not settings.rate_limit_enabled:
        def _noop(func):
            return func

        return _noop

    limit_value = f"{calls_per_minute or settings.rate_limit_per_minute}/minute"
    return limiter.limit(limit_value)


def setup_rate_limiting(app: FastAPI) -> None:
    """
    Configure rate limiting for the FastAPI app using SlowAPI.
    
    Sets up SlowAPI limiter, middleware, and exception handler.
    Respects RATE_LIMIT_ENABLED and RATE_LIMIT_PER_MINUTE settings.
    """
    if not settings.rate_limit_enabled:
        logger.info("Rate limiting is disabled")
        return
    
    default_limit = f"{settings.rate_limit_per_minute}/minute"
    limiter.default_limits = [default_limit]
    
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    
    logger.info(
        "Rate limiting enabled",
        extra={
            "requests_per_minute": settings.rate_limit_per_minute,
            "default_limit": default_limit,
        },
    )


__all__ = ["limiter", "setup_rate_limiting", "get_rate_limit_decorator"]
