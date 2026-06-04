# -*- coding: utf-8 -*-
"""API Key authentication middleware."""
import os, logging, secrets
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_KEY", "")
DEV_MODE = os.getenv("DEV_MODE", "").lower() in ("1", "true", "yes")

# Auto-generate a key when none is configured and dev mode is off,
# so write endpoints are never accidentally exposed.
if not API_KEY and not DEV_MODE:
    API_KEY = secrets.token_urlsafe(24)
    logger.warning(
        "[security] No API_KEY configured and DEV_MODE is off. "
        "Auto-generated key: %s  "
        "Set API_KEY in .env to make it persistent.",
        API_KEY,
    )


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Enforce X-API-Key on write endpoints."""

    async def dispatch(self, request: Request, call_next):
        # Explicit dev mode => allow everything
        if DEV_MODE:
            return await call_next(request)

        # Read-only methods pass without a key
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        key = request.headers.get("x-api-key", "")
        if key != API_KEY:
            return JSONResponse(
                {"status": "error", "message": "Missing or invalid API key"},
                status_code=401,
            )

        return await call_next(request)
