from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.cache import get_cache
from app.core.config import get_settings
from app.core.exceptions import AppError, app_error_handler, setup_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware
from app.core.rate_limit import setup_rate_limiting
from app.routers import health_router, household_router, pantry_router

logger = logging.getLogger(__name__)


def create_app(*, settings: Any | None = None) -> FastAPI:
    resolved_settings = get_settings() if settings is None else settings
    configure_logging(app_env=resolved_settings.app_env)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting app", extra={"app_name": resolved_settings.app_name, "app_env": resolved_settings.app_env})
        yield
        logger.info("Shutting down app")
        get_cache().clear()

    app = FastAPI(title=resolved_settings.app_name, lifespan=lifespan)

    app.add_middleware(RequestLoggingMiddleware)

    @app.middleware("http")
    async def request_timing_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["x-app-name"] = resolved_settings.app_name
        return response

    setup_exception_handlers(app)
    app.add_exception_handler(AppError, app_error_handler)
    setup_rate_limiting(app)

    app.include_router(health_router)
    app.include_router(household_router)
    app.include_router(pantry_router)

    @app.get("/", include_in_schema=False)
    def get_root() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    return app


app = create_app()


__all__ = ["app", "create_app"]
