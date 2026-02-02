# Custom exception handlers

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base for domain errors that map to HTTP responses."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail or {"message": message}


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", **kwargs: Any) -> None:
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND, **kwargs)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized", **kwargs: Any) -> None:
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED, **kwargs)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden", **kwargs: Any) -> None:
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN, **kwargs)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation error", **kwargs: Any) -> None:
        super().__init__(message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, **kwargs)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict", **kwargs: Any) -> None:
        super().__init__(message, status_code=status.HTTP_409_CONFLICT, **kwargs)


def http_exception_from_app_error(exc: AppError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "AppError handled",
        extra={"path": str(request.url.path), "status_code": exc.status_code, "message": exc.message},
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


__all__ = [
    "AppError",
    "ConflictError",
    "ForbiddenError",
    "NotFoundError",
    "UnauthorizedError",
    "ValidationError",
    "app_error_handler",
    "http_exception_from_app_error",
]
