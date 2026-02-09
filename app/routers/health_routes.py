from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.logging import get_logger

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


class HealthResponse(BaseModel):
    status: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    logger.info("Health check requested")
    return HealthResponse(status="ok")


__all__ = ["router"]
