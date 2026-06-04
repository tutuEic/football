# -*- coding: utf-8 -*-
"""Simple in-memory rate limiting middleware."""
import time
import logging
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("rate_limit")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiter with stricter limits on search endpoints."""

    def __init__(self, app, default_limit: int = 120, search_limit: int = 30, window: float = 60.0):
        super().__init__(app)
        self.default_limit = default_limit
        self.search_limit = search_limit
        self.window = window
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _clean(self, key: str, now: float):
        cutoff = now - self.window
        self._hits[key] = [t for t in self._hits[key] if t > cutoff]

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        path = request.url.path
        now = time.time()

        #  Use a stricter key for search-like endpoints
        if "/search" in path:
            key = f"{ip}:search"
            limit = self.search_limit
        else:
            key = f"{ip}:default"
            limit = self.default_limit

        self._clean(key, now)
        count = len(self._hits[key])

        logger.info("[rate-limit] ip=%s path=%s key=%s count=%d limit=%d", ip, path, key, count, limit)

        if count >= limit:
            return JSONResponse(
                {"status": "error", "message": "Rate limit exceeded. Try again later."},
                status_code=429,
            )

        self._hits[key].append(now)
        return await call_next(request)
