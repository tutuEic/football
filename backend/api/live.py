"""
Live API - fixtures, live scores, WebSocket
"""
import sys, os
from security import API_KEY, DEV_MODE
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from datetime import date, timedelta
from data.pipeline_fixtures import get_upcoming_matches
from data.service_live import get_today_status, poller

router = APIRouter(tags=["live"])
logger = logging.getLogger(__name__)

# WebSocket connections
_ws_clients: list[WebSocket] = []


@router.get("/fixtures/upcoming")
def api_upcoming(league_code: str = None, days: int = 7, limit: int = 100):
    """Upcoming fixtures."""
    matches = get_upcoming_matches(league_code=league_code, days=days, limit=limit)
    return {"matches": matches, "count": len(matches)}


@router.get("/fixtures/today")
def api_today():
    """All matches today (including live status)"""
    matches = get_today_status()
    live_count = sum(1 for m in matches if m.get("status") in ("live", "today"))
    scheduled_count = sum(1 for m in matches if m.get("status") == "scheduled")
    return {
        "matches": matches,
        "count": len(matches),
        "live": live_count,
        "scheduled": scheduled_count,
        "date": date.today().isoformat(),
    }


@router.get("/fixtures/league/{league_code}")
def api_league_fixtures(league_code: str, days: int = 30):
    """League fixtures for the coming period."""
    matches = get_upcoming_matches(league_code=league_code, days=days, limit=500)
    return {"league_code": league_code, "matches": matches, "count": len(matches)}


@router.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    """WebSocket: push live score changes to frontend (requires token via subprotocol)"""
    if not DEV_MODE:
        token = None
        proto = ws.headers.get("sec-websocket-protocol", "")
        if proto:
            parts = [p.strip() for p in proto.split(",")]
            for p in parts:
                if p != "json":
                    token = p
                    break
        if not token or not secrets.compare_digest(token, API_KEY):
            await ws.close(code=4001, reason="Unauthorized")
            return
    
    await ws.accept()
    _ws_clients.append(ws)
    loop = asyncio.get_running_loop()

    # Sync callback that schedules async push on the event loop
    def _on_poll(data):
        try:
            asyncio.run_coroutine_threadsafe(
                ws.send_json({"type": "live_update", "matches": data, "timestamp": date.today().isoformat()}),
                loop,
            )
        except Exception:
            logger.debug("Failed to push live update to ws client", exc_info=True)

    poller.register_callback(_on_poll)

    try:
        # Send initial state
        initial = get_today_status()
        await ws.send_json({"type": "initial", "matches": initial, "count": len(initial)})

        # Keep connection alive, listen for client messages
        while True:
            msg = await ws.receive_text()
            if msg == "refresh":
                updated = get_today_status()
                await ws.send_json({"type": "update", "matches": updated, "count": len(updated)})

    except WebSocketDisconnect:
        pass
    finally:
        if ws in _ws_clients:
            _ws_clients.remove(ws)
        # Remove callback from poller to avoid stale references
        if _on_poll in poller.callbacks:
            poller.callbacks.remove(_on_poll)


@router.get("/live/status")
def api_live_status():
    """Live service status"""
    today_matches = get_today_status()
    live_now = [m for m in today_matches if m.get("status") in ("live", "today")]
    return {
        "poller_running": poller.running,
        "ws_clients": len(_ws_clients),
        "today_matches": len(today_matches),
        "live_now": len(live_now),
        "live_matches": [
            {
                "home": m["home_team"], "away": m["away_team"],
                "score": f"{m.get('home_score','?')}-{m.get('away_score','?')}",
                "minute": m.get("minute", 0),
                "league": m["league_code"],
            }
            for m in live_now
        ],
    }
