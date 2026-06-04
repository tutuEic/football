# -*- coding: utf-8 -*-
"""Football Sandbox API — FastAPI 主入口"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import players, predict, sandbox, odds, models, matches, teams, clubs, live, fixtures, worldcup
from security import APIKeyMiddleware
from rate_limit import RateLimitMiddleware

app = FastAPI(
    title="Football Prediction Sandbox API",
    version="0.3.1",
    description="足球预测沙盘系统 — 实时赛程 + 蒙特卡洛模拟 + 概率输出"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
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
    





@app.post("/api/refresh/cl")
def refresh_cl():
    """???????"""
    from data.pipeline_cl import run_pipeline
    results, fixtures = run_pipeline()
    return {
        "status": "ok",
        "completed": len(results),
        "upcoming": len(fixtures),
    }


@app.post("/api/refresh/fixtures")
def refresh_fixtures():
    """?????????"""
    from data.pipeline_fixtures import run_pipeline
    run_pipeline()
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
