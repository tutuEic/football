# -*- coding: utf-8 -*-
"""API Key authentication middleware."""
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


API_KEY = os.getenv("API_KEY", "")


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Enforce X-API-Key on write endpoints."""

    async def dispatch(self, request: Request, call_next):
        # No key configured => dev mode, allow all
        if not API_KEY:
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
