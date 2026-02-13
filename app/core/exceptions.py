from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Application error with HTTP status and detail for API responses."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.headers = headers or {}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle AppError by returning a JSON response with status and detail."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "status_code": exc.status_code},
        headers=exc.headers,
    )


def create_unhandled_exception_handler(
    *,
    app_env: str,
    debug: bool | None = None,
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    """
    Return an async exception handler for unhandled Exception.

    When app_env is "development" or debug is True, the response includes the
    exception message; otherwise a generic message is returned.
    """
    show_message = debug if debug is not None else (app_env.lower() == "development")

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "message": str(exc) if show_message else "An unexpected error occurred",
            },
        )

    return handler


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Set up global exception handlers for the FastAPI app.

    This configures custom handling for standard HTTP errors, data validation errors,
    and all uncaught exceptions to produce controlled and informative JSON responses.
    """

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """
        Handle HTTP exceptions (e.g., 404 Not Found, 403 Forbidden).

        Returns a JSON response with the original status code and error detail.
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        Handle validation errors (e.g., request payload/data is invalid with respect to OpenAPI schema).

        Returns a JSON response containing details about validation errors.
        """
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation error",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Handle all unhandled and unexpected exceptions.

        Logs the complete error to the server logs. If the application is in debug mode,
        the error message is revealed in the response for debugging purposes.
        Otherwise, a generic error message is shown to the client.
        """
        logger.error("Unexpected error: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "message": (
                    str(exc) if settings.debug else "An unexpected error occurred"
                ),
            },
        )


__all__ = [
    "AppError",
    "app_error_handler",
    "create_unhandled_exception_handler",
    "setup_exception_handlers",
]
