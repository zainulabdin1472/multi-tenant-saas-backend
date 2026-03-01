"""Logging middleware - logs HTTP method, endpoint, user_id, tenant_id, timestamp."""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("teamflow")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log each request with method, path, user/tenant from JWT if available."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        user_id: str | None = None
        tenant_id: str | None = None
        try:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                from app.core.security import decode_token

                token = auth_header.split(" ", 1)[1]
                payload = decode_token(token)
                if payload:
                    user_id = payload.get("sub")
                    tenant_id = payload.get("tenant_id")
        except Exception:
            pass
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "method=%s path=%s user_id=%s tenant_id=%s status=%d duration_ms=%.2f",
            request.method,
            request.url.path,
            user_id or "-",
            tenant_id or "-",
            response.status_code,
            duration_ms,
        )
        return response
