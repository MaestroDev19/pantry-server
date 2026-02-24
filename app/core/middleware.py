from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request/response logging with trace IDs and latency tracking.
    
    Generates a unique trace ID for each request and logs:
    - Request method, path, query params
    - Response status code
    - Request latency in milliseconds
    - Trace ID for correlation
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        
        start_time = time.time()
        
        method = request.method
        path = request.url.path
        query_params = dict(request.query_params)
        
        logger.info(
            "Request started",
            extra={
                "trace_id": trace_id,
                "method": method,
                "path": path,
                "query_params": query_params,
                "client_host": request.client.host if request.client else None,
            },
        )
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            
            latency_ms = (time.time() - start_time) * 1000
            
            logger.info(
                "Request completed",
                extra={
                    "trace_id": trace_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "latency_ms": round(latency_ms, 2),
                },
            )
            
            response.headers["X-Trace-Id"] = trace_id
            response.headers["X-Response-Time-Ms"] = str(round(latency_ms, 2))
            
            return response
            
        except Exception as exc:
            latency_ms = (time.time() - start_time) * 1000
            
            logger.error(
                "Request failed",
                extra={
                    "trace_id": trace_id,
                    "method": method,
                    "path": path,
                    "error": str(exc),
                    "latency_ms": round(latency_ms, 2),
                },
                exc_info=True,
            )
            
            raise


__all__ = ["RequestLoggingMiddleware"]
