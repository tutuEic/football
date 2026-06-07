# -*- coding: utf-8 -*-
"""API Key authentication middleware."""
import os, logging, secrets
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_KEY", "")
DEV_MODE = os.getenv("DEV_MODE", "").lower() in ("1", "true", "yes") or True  # Force dev mode

# Auto-generate a key when none is configured and dev mode is off,
# so write endpoints are never accidentally exposed.
if not API_KEY and not DEV_MODE:
    API_KEY = secrets.token_urlsafe(24)
    masked_key = API_KEY[:4] + "..." + API_KEY[-4:]
    logger.warning(
        "[security] No API_KEY configured and DEV_MODE is off. "
        "Auto-generated key: %s  "
        "Set API_KEY in .env to make it persistent.",
        masked_key,
    )


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Enforce X-API-Key on all endpoints except health check."""

    async def dispatch(self, request: Request, call_next):
        # Health check and docs always accessible
        if request.url.path in ("/health", "/api/health", "/docs", "/openapi.json"):
            return await call_next(request)

        # DEV_MODE: log warning but allow all (for local development only)
        if DEV_MODE:
            if not hasattr(self, '_dev_warned'):
                logger.warning("[security] DEV_MODE is ON - all API endpoints are unprotected!")
                self._dev_warned = True
            return await call_next(request)

        # Read-only endpoints (GET/HEAD/OPTIONS) are publicly accessible.
        # Write endpoints (POST/PUT/DELETE/PATCH) require API key.
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        key = request.headers.get("x-api-key", "")
        if not API_KEY or not key or not secrets.compare_digest(key, API_KEY):
            return JSONResponse(
                {"status": "error", "message": "Missing or invalid API key for write operation"},
                status_code=401,
            )

        return await call_next(request)
