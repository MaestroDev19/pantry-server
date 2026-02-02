from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.errors import create_unhandled_exception_handler
from app.core.exceptions import AppError, app_error_handler
from app.core.logging import configure_logging
from app.routers import health_router

logger = logging.getLogger(__name__)


def create_app(*, settings: Any | None = None) -> FastAPI:
    resolved_settings = get_settings() if settings is None else settings
    configure_logging(app_env=resolved_settings.app_env)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting app", extra={"app_name": resolved_settings.app_name, "app_env": resolved_settings.app_env})
        yield
        logger.info("Shutting down app")

    app = FastAPI(title=resolved_settings.app_name, lifespan=lifespan)

    @app.middleware("http")
    async def request_timing_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["x-app-name"] = resolved_settings.app_name
        return response

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, create_unhandled_exception_handler(app_env=resolved_settings.app_env))

    app.include_router(health_router)

    @app.get("/", include_in_schema=False)
    def get_root() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    return app


app = create_app()


__all__ = ["app", "create_app"]
