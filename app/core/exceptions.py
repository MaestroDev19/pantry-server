from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)


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
        logger.error(f"Unexpected error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "message": (
                    str(exc) if settings.debug else "An unexpected error occurred"
                ),
            },
        )


__all__ = ["setup_exception_handlers"]
