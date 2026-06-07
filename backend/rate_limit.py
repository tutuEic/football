# -*- coding: utf-8 -*-
"""Simple in-memory rate limiting middleware."""
import time
import os
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
        filtered = [t for t in self._hits[key] if t > cutoff]
        if filtered:
            self._hits[key] = filtered
        else:
            # Remove empty entries to prevent memory leak
            self._hits.pop(key, None)

    # Set TRUST_PROXY=true env var ONLY when behind a trusted reverse proxy.
    _TRUST_PROXY = os.getenv("TRUST_PROXY", "").lower() in ("1", "true", "yes")

    def _get_client_ip(self, request: Request) -> str:
        """Get real client IP. Only trusts X-Forwarded-For behind a known proxy."""
        if self._TRUST_PROXY:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        ip = self._get_client_ip(request)
        path = request.url.path
        now = time.time()

        # Use stricter key for search-like endpoints
        if path.startswith("/api/") and "/search" in path:
            key = f"{ip}:search"
            limit = self.search_limit
        else:
            key = f"{ip}:default"
            limit = self.default_limit

        self._clean(key, now)
        count = len(self._hits[key])

        logger.debug("[rate-limit] ip=%s path=%s key=%s count=%d limit=%d", ip, path, key, count, limit)

        if count >= limit:
            return JSONResponse(
                {"status": "error", "message": "Rate limit exceeded. Try again later."},
                status_code=429,
            )

        self._hits[key].append(now)
        return await call_next(request)
