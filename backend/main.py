# -*- coding: utf-8 -*-
"""Football Sandbox API - FastAPI main entry."""
import sys, os, asyncio, logging
# Ensure the backend package is importable when running main.py directly.
if os.path.dirname(__file__) not in sys.path:
    sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import players, predict, sandbox, odds, models, matches, teams, clubs, live, fixtures, worldcup
from security import APIKeyMiddleware
from rate_limit import RateLimitMiddleware
from config import MYSQL_USER, MYSQL_PASS

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Football Prediction Sandbox API",
    version="0.3.1",
    description="Football prediction sandbox system with Monte Carlo simulation."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "Accept"],
)

app.add_middleware(RateLimitMiddleware, default_limit=120, search_limit=30)
app.add_middleware(APIKeyMiddleware)

app.include_router(players.router, prefix="/api")
app.include_router(predict.router, prefix="/api")
app.include_router(sandbox.router, prefix="/api")
app.include_router(odds.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(matches.router, prefix="/api")
app.include_router(teams.router, prefix="/api")
app.include_router(clubs.router, prefix="/api")
app.include_router(live.router, prefix="/api")
app.include_router(fixtures.router, prefix="/api")
app.include_router(worldcup.router, prefix="/api")


@app.on_event("startup")
async def startup():
    from data.service_live import poller
    poller.start()
    print("[api] Live score poller started")

    # Warn about insecure MySQL credentials
    if MYSQL_USER == "root":
        logger.warning("[security] MYSQL_USER is set to 'root'. Use a dedicated application user instead.")
    if not MYSQL_PASS:
        logger.warning("[security] MYSQL_PASS is empty. Set a strong password in .env.")


@app.post("/api/refresh/cl")
async def refresh_cl():
    """Run CL pipeline in background thread."""
    from data.pipeline_cl import run_pipeline
    loop = asyncio.get_event_loop()
    results, fixtures = await loop.run_in_executor(None, run_pipeline)
    return {
        "status": "ok",
        "completed": len(results),
        "upcoming": len(fixtures),
    }


@app.post("/api/refresh/fixtures")
async def refresh_fixtures():
    """Run fixtures pipeline in background thread."""
    from data.pipeline_fixtures import run_pipeline
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, run_pipeline)
    return {"status": "ok"}

@app.get("/api/health")
def health():
    from engine.predictor import list_available_models
    from data.service_live import get_today_status
    today = len(get_today_status())
    return {
        "status": "ok",
        "version": "0.3.1",
        "models_trained": len(list_available_models()),
        "today_matches": today,
    }
