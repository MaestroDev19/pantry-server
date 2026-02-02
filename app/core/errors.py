from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def create_unhandled_exception_handler(*, app_env: str) -> Callable[[Request, Exception], JSONResponse]:
    def handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", extra={"path": str(request.url.path)})

        is_production = app_env.lower() in {"prod", "production"}
        detail = "Internal Server Error" if is_production else repr(exc)
        return JSONResponse(status_code=500, content={"detail": detail})

    return handler


__all__ = ["create_unhandled_exception_handler"]
